"""
Document Integration Service - Bridges document uploads with chat orchestration.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.db.models import Document, Claim
from app.services.session_store import get_session_store
from app.core.logging import logger


# Session key prefix (matching chat.py)
STATE_KEY_PREFIX = "conversation_state:"


def get_documents_for_claim(db: Session, claim_id: str) -> List[Dict[str, Any]]:
    """
    Get all documents with extracted entities for a claim.

    Args:
        db: Database session
        claim_id: The claim ID to get documents for

    Returns:
        List of document dictionaries with extracted entities
    """
    documents = db.query(Document).filter(Document.claim_id == claim_id).all()
    return [
        {
            "doc_id": str(doc.doc_id),
            "doc_type": doc.doc_type.value,
            "filename": doc.filename,
            "file_path": doc.storage_url,
            "extracted_entities": doc.extracted_entities or {},
            "uploaded_at": doc.uploaded_at.isoformat(),
            "verification_status": getattr(doc, 'verification_status', None),
        }
        for doc in documents
    ]


def notify_chat_of_document_upload(
    thread_id: str,
    claim_id: str,
    doc_id: str,
    doc_type: str,
    extracted_entities: Dict[str, Any],
) -> bool:
    """
    Notify the chat session that a document was uploaded.

    Updates the conversation state to include the new document data.

    Args:
        thread_id: The chat thread ID
        claim_id: The claim ID
        doc_id: The uploaded document ID
        doc_type: The document type (e.g., "police_report")
        extracted_entities: OCR extracted data from the document

    Returns:
        True if the session was updated, False if session not found
    """
    session_store = get_session_store()
    state_key = f"{STATE_KEY_PREFIX}{thread_id}"
    state = session_store.get(state_key)

    if not state:
        logger.warning(f"No session found for thread {thread_id} to notify of document upload")
        return False

    # Add document to state
    documents = state.get("uploaded_documents", [])
    documents.append({
        "doc_id": doc_id,
        "doc_type": doc_type,
        "extracted_entities": extracted_entities,
        "claim_id": claim_id,
    })

    state["uploaded_documents"] = documents
    state["pending_document_review"] = True

    session_store.set(state_key, state, ttl_hours=24)
    logger.info(f"Notified chat session {thread_id} of document upload: {doc_id} ({doc_type})")
    return True


def merge_document_entities_to_collected_fields(
    collected_fields: Dict[str, Any],
    documents: List[Dict[str, Any]],
    required_fields: List[str],
) -> Dict[str, Any]:
    """
    Merge extracted entities from documents into collected fields.

    Only adds fields that are in required_fields and not already collected.

    Args:
        collected_fields: Currently collected claim fields
        documents: List of document dicts with extracted_entities
        required_fields: List of fields required for the claim

    Returns:
        Updated collected_fields dict with merged document data
    """
    merged = dict(collected_fields)

    # Field mapping from OCR extraction keys to claim field names
    ENTITY_TO_FIELD_MAP = {
        # Dates
        "dates": ["incident_date", "service_date"],
        "incident_date": ["incident_date"],
        "service_date": ["service_date"],
        # Location
        "incident_location": ["incident_location"],
        "location": ["incident_location"],
        # Amounts
        "amounts": ["estimated_damage", "loss_amount", "billed_amount"],
        "total_amount": ["estimated_damage", "loss_amount", "billed_amount"],
        "estimated_damage": ["estimated_damage"],
        "billed_amount": ["billed_amount"],
        # Document IDs
        "document_ids": ["police_report_number"],
        "police_report_number": ["police_report_number"],
        # Parties
        "parties": ["other_party_info"],
        "other_party_info": ["other_party_info"],
        # Provider info (medical)
        "provider_name": ["provider_name"],
        "provider_npi": ["provider_npi"],
    }

    fields_added = []

    for doc in documents:
        entities = doc.get("extracted_entities", {})

        # Skip error/skipped documents
        if entities.get("status") in ["error", "skipped"]:
            continue

        for entity_key, field_names in ENTITY_TO_FIELD_MAP.items():
            entity_value = entities.get(entity_key)
            if entity_value is not None and entity_value != "":
                for field_name in field_names:
                    # Only add if field is required and not already collected
                    if field_name in required_fields and field_name not in merged:
                        # Handle list values (take first item if list)
                        if isinstance(entity_value, list) and len(entity_value) > 0:
                            merged[field_name] = entity_value[0]
                        else:
                            merged[field_name] = entity_value
                        fields_added.append(field_name)

        # Direct mappings for specific document types
        doc_type = doc.get("doc_type")
        if doc_type == "police_report" and "police_report_number" not in merged:
            # Try to get police report number from document_ids
            doc_ids = entities.get("document_ids")
            if doc_ids:
                if isinstance(doc_ids, list) and len(doc_ids) > 0:
                    merged["police_report_number"] = doc_ids[0]
                    fields_added.append("police_report_number")
                elif isinstance(doc_ids, str):
                    merged["police_report_number"] = doc_ids
                    fields_added.append("police_report_number")

    if fields_added:
        logger.info(f"Merged fields from documents: {fields_added}")

    return merged


def generate_document_confirmation_message(
    doc_type: str,
    extracted_entities: Dict[str, Any],
) -> str:
    """
    Generate a confirmation message for the user after document upload.

    Args:
        doc_type: The type of document uploaded
        extracted_entities: The extracted data from OCR

    Returns:
        A user-friendly confirmation message
    """
    # Check if extraction was successful
    status = extracted_entities.get("status", "processed")
    if status in ["error", "skipped"]:
        reason = extracted_entities.get("reason", "unknown error")
        return f"I received your {doc_type.replace('_', ' ')}, but I wasn't able to automatically extract the information. Could you please provide the details manually?"

    # Build confirmation based on document type
    doc_type_display = doc_type.replace("_", " ").title()

    # Extract key fields based on document type
    extracted_info = []

    if doc_type == "police_report":
        if extracted_entities.get("document_ids"):
            ids = extracted_entities["document_ids"]
            report_num = ids[0] if isinstance(ids, list) else ids
            extracted_info.append(f"Report Number: {report_num}")
        if extracted_entities.get("incident_date") or extracted_entities.get("dates"):
            date = extracted_entities.get("incident_date") or (extracted_entities.get("dates", [None])[0] if isinstance(extracted_entities.get("dates"), list) else extracted_entities.get("dates"))
            if date:
                extracted_info.append(f"Incident Date: {date}")
        if extracted_entities.get("incident_location") or extracted_entities.get("location"):
            location = extracted_entities.get("incident_location") or extracted_entities.get("location")
            extracted_info.append(f"Location: {location}")

    elif doc_type in ["repair_estimate", "invoice"]:
        if extracted_entities.get("total_amount") or extracted_entities.get("amounts"):
            amount = extracted_entities.get("total_amount") or (extracted_entities.get("amounts", [None])[0] if isinstance(extracted_entities.get("amounts"), list) else extracted_entities.get("amounts"))
            if amount:
                extracted_info.append(f"Amount: ${amount}")
        if extracted_entities.get("dates"):
            dates = extracted_entities["dates"]
            date = dates[0] if isinstance(dates, list) else dates
            extracted_info.append(f"Date: {date}")

    elif doc_type == "incident_photos":
        if extracted_entities.get("summary"):
            extracted_info.append(f"Description: {extracted_entities['summary']}")

    # Build the message
    if extracted_info:
        info_text = "\n".join(f"  - {info}" for info in extracted_info)
        message = f"I've received and processed your {doc_type_display}. Here's what I extracted:\n{info_text}\n\nDoes this look correct?"
    else:
        message = f"I've received your {doc_type_display} and it has been processed successfully."

    return message
