"""
OCR/Vision extraction service.
"""
from __future__ import annotations

import base64
import json
from typing import Any, Dict, Optional

import httpx
from sqlalchemy.orm import Session

from app.core import logger, settings
from app.db.models import SystemSettings
from app.services.ocr_schemas import get_extraction_prompt_for_doc_type, validate_extraction


def _get_setting(db: Optional[Session], key: str, default: Any) -> Any:
    if not db:
        return default
    setting = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    return setting.value if setting else default


def _extract_json(content: str) -> Dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = content[start : end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                pass
    return {"raw_output": content, "parse_error": "Failed to parse JSON"}


async def extract_document_entities(
    file_path: str,
    doc_type: str,
    content_type: Optional[str],
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Extract structured entities from an uploaded document image."""
    if not content_type or not content_type.startswith("image/"):
        return {"status": "skipped", "reason": "unsupported_content_type"}

    llm_provider = _get_setting(db, "llm_provider", "ollama")
    
    try:
        with open(file_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
    except OSError as exc:
        logger.error(f"OCR read failed for {file_path}: {exc}")
        return {"status": "error", "reason": "file_read_failed"}

    # Get document-specific extraction prompt
    prompt_text = get_extraction_prompt_for_doc_type(doc_type)

    content = ""

    if llm_provider == "bedrock":
        import boto3
        bedrock_runtime = boto3.client(
            service_name="bedrock-runtime",
            region_name=settings.AWS_REGION if hasattr(settings, "AWS_REGION") else "us-east-1"
        )
        
        # Claude 3 Sonnet (or Haiku) model ID
        model_id = _get_setting(db, "bedrock_model", "anthropic.claude-3-sonnet-20240229-v1:0")
        
        bedrock_payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": content_type,
                                "data": encoded,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt_text,
                        }
                    ],
                }
            ],
        }
        
        try:
            response = bedrock_runtime.invoke_model(
                modelId=model_id,
                body=json.dumps(bedrock_payload),
            )
            response_body = json.loads(response.get("body").read())
            content = response_body.get("content", [])[0].get("text", "")
            
        except Exception as exc:
            logger.error(f"Bedrock OCR request failed: {exc}")
            return {"status": "error", "reason": "bedrock_request_failed"}

    else:
        # Fallback to Ollama
        ollama_endpoint = _get_setting(db, "ollama_endpoint", settings.OLLAMA_BASE_URL).rstrip("/")
        vision_model = _get_setting(db, "ollama_vision_model", settings.OLLAMA_VISION_MODEL)
        
        payload = {
            "model": vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt_text,
                    "images": [encoded],
                }
            ],
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(f"{ollama_endpoint}/api/chat", json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error(f"OCR request failed: {exc}")
            return {"status": "error", "reason": "request_failed"}

        data = response.json()
        content = data.get("message", {}).get("content", "")

    if not content:
        return {"status": "error", "reason": "empty_response"}

    extracted = _extract_json(content)

    # Validate and normalize the extraction using document-specific schema
    validated = validate_extraction(doc_type, extracted)
    validated.setdefault("status", "processed")
    validated["doc_type"] = doc_type

    logger.info(f"OCR extraction completed for {doc_type}: confidence={validated.get('confidence', 'N/A')}")

    return validated
