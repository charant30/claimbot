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

    ollama_endpoint = _get_setting(db, "ollama_endpoint", settings.OLLAMA_BASE_URL).rstrip("/")
    vision_model = _get_setting(db, "ollama_vision_model", settings.OLLAMA_VISION_MODEL)

    try:
        with open(file_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
    except OSError as exc:
        logger.error(f"OCR read failed for {file_path}: {exc}")
        return {"status": "error", "reason": "file_read_failed"}

    prompt = (
        "You are an OCR extraction assistant. "
        f"Extract structured details from the uploaded {doc_type} document. "
        "Return ONLY valid JSON with keys: summary, dates, parties, amounts, "
        "document_ids, incident_location, and confidence (0-1). "
        "Use null when data is missing."
    )

    payload = {
        "model": vision_model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
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
    extracted.setdefault("status", "processed")
    return extracted
