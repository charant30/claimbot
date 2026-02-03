"""
Document Flow State Machine - Manages document requirements and verification flow.
"""
from typing import List, Dict, Any, Optional, NamedTuple
from dataclasses import dataclass, field
from enum import Enum

from app.core.logging import logger


class DocumentStatus(str, Enum):
    """Status of a document in the flow."""
    NOT_UPLOADED = "not_uploaded"
    UPLOADED = "uploaded"
    VERIFIED = "verified"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"


@dataclass
class DocumentRequirement:
    """A required document in the flow."""
    doc_type: str
    display_name: str
    required_fields: List[str] = field(default_factory=list)
    is_conditional: bool = False
    condition: Optional[str] = None  # e.g., "!police_report.location_confirmed"


@dataclass
class DocumentFlowStatus:
    """Current status of the document collection flow."""
    required_documents: List[str]
    uploaded_documents: Dict[str, dict]
    verified_documents: Dict[str, dict]
    current_document: Optional[str]
    all_required_present: bool
    next_required: Optional[str]
    progress_pct: float

    def to_dict(self) -> dict:
        return {
            "required_documents": self.required_documents,
            "uploaded_count": len(self.uploaded_documents),
            "verified_count": len(self.verified_documents),
            "current_document": self.current_document,
            "all_required_present": self.all_required_present,
            "next_required": self.next_required,
            "progress_pct": self.progress_pct,
        }


@dataclass
class DocumentRequest:
    """A request for a document from the user."""
    doc_type: str
    request_message: str
    is_required: bool = True


# Default document requirements by product line and incident type
DEFAULT_DOCUMENT_FLOWS = {
    "auto": {
        "collision": [
            # Incident photos are MANDATORY - used to verify the incident
            DocumentRequirement(
                doc_type="incident_photos",
                display_name="Accident Photos",
                required_fields=[],
                is_conditional=False,
            ),
            # Police report is OPTIONAL - can substitute for photos
            DocumentRequirement(
                doc_type="police_report",
                display_name="Police Report (Optional)",
                required_fields=["police_report_number", "incident_date"],
                is_conditional=True,
                condition="!incident_photos",  # Only needed if no photos
            ),
            DocumentRequirement(
                doc_type="repair_estimate",
                display_name="Repair Estimate",
                required_fields=["total_amount"],
            ),
            DocumentRequirement(
                doc_type="invoice",
                display_name="Invoice",
                required_fields=["total_amount"],
                is_conditional=True,
                condition="repair_complete == true",
            ),
        ],
        "theft": [
            DocumentRequirement(
                doc_type="police_report",
                display_name="Police Report",
                required_fields=["police_report_number", "incident_date"],
            ),
            DocumentRequirement(
                doc_type="incident_photos",
                display_name="Photos of Damage/Scene",
                required_fields=[],
            ),
        ],
        "comprehensive": [
            DocumentRequirement(
                doc_type="incident_photos",
                display_name="Damage Photos",
                required_fields=[],
            ),
            DocumentRequirement(
                doc_type="repair_estimate",
                display_name="Repair Estimate",
                required_fields=["total_amount"],
            ),
        ],
    },
    "home": {
        "fire": [
            DocumentRequirement(
                doc_type="incident_photos",
                display_name="Damage Photos",
                required_fields=[],
            ),
            DocumentRequirement(
                doc_type="repair_estimate",
                display_name="Contractor Estimate",
                required_fields=["total_amount"],
            ),
        ],
        "water": [
            DocumentRequirement(
                doc_type="incident_photos",
                display_name="Damage Photos",
                required_fields=[],
            ),
            DocumentRequirement(
                doc_type="repair_estimate",
                display_name="Repair Estimate",
                required_fields=["total_amount"],
            ),
        ],
        "theft": [
            DocumentRequirement(
                doc_type="police_report",
                display_name="Police Report",
                required_fields=["police_report_number"],
            ),
            DocumentRequirement(
                doc_type="incident_photos",
                display_name="Photos of Damage",
                required_fields=[],
            ),
        ],
    },
    "medical": {
        "default": [
            DocumentRequirement(
                doc_type="eob",
                display_name="Explanation of Benefits",
                required_fields=["service_date", "billed_amount"],
            ),
            DocumentRequirement(
                doc_type="invoice",
                display_name="Medical Invoice",
                required_fields=["total_amount"],
                is_conditional=True,
                condition="eob.patient_responsibility > 0",
            ),
        ],
    },
}

# Document request messages
DOCUMENT_REQUEST_MESSAGES = {
    "police_report": "If you have a police report, please upload it (optional). This helps verify incident details.",
    "incident_photos": "Please upload photos of the damage. Clear photos from multiple angles are required to verify and assess the incident.",
    "repair_estimate": "Please upload a repair estimate from a qualified repair shop. This should include itemized costs for parts and labor.",
    "invoice": "Please upload the invoice for the completed repairs. This should show the final amount paid.",
    "eob": "Please upload your Explanation of Benefits (EOB) from your insurance provider. You can usually find this in your online portal or mail.",
    "medical_record": "Please upload relevant medical records related to this claim.",
}


def get_required_documents(
    product_line: str,
    incident_type: Optional[str] = None,
    collected_fields: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Get the list of required documents for a product/incident combination.

    Args:
        product_line: The product line (auto, home, medical)
        incident_type: Optional incident type for more specific requirements
        collected_fields: Current collected fields to evaluate conditions

    Returns:
        List of required document types in order
    """
    product_flows = DEFAULT_DOCUMENT_FLOWS.get(product_line, {})

    # Try specific incident type first, then default
    incident_type = (incident_type or "default").lower()
    requirements = product_flows.get(incident_type) or product_flows.get("default", [])

    # If no specific flow found, use a generic one
    if not requirements:
        if product_line == "auto":
            requirements = product_flows.get("collision", [])
        elif product_line == "home":
            requirements = product_flows.get("fire", [])
        elif product_line == "medical":
            requirements = DEFAULT_DOCUMENT_FLOWS.get("medical", {}).get("default", [])

    # Filter out conditional documents that don't apply
    required_docs = []
    for req in requirements:
        if req.is_conditional:
            # For now, include conditional docs - full condition evaluation would go here
            # In production, evaluate req.condition against collected_fields
            if _evaluate_condition(req.condition, collected_fields):
                required_docs.append(req.doc_type)
        else:
            required_docs.append(req.doc_type)

    return required_docs


def _evaluate_condition(condition: Optional[str], collected_fields: Optional[Dict[str, Any]]) -> bool:
    """
    Evaluate a condition string against collected fields.

    For now, this returns True by default (include conditional documents).
    In production, implement proper condition parsing and evaluation.
    """
    if not condition:
        return True

    # Simple condition evaluation
    # Format: "field_name.sub_field == value" or "!field_name.sub_field"
    collected_fields = collected_fields or {}

    try:
        if condition.startswith("!"):
            # Negation: !police_report.location_confirmed
            field_path = condition[1:].strip()
            value = _get_nested_value(collected_fields, field_path)
            return not bool(value)
        elif "==" in condition:
            # Equality: police_report.location_confirmed == false
            parts = condition.split("==")
            field_path = parts[0].strip()
            expected = parts[1].strip().lower()
            value = _get_nested_value(collected_fields, field_path)
            if expected in ["true", "false"]:
                return str(value).lower() == expected
            return str(value) == expected
        elif ">" in condition:
            # Greater than: eob.patient_responsibility > 0
            parts = condition.split(">")
            field_path = parts[0].strip()
            threshold = float(parts[1].strip())
            value = _get_nested_value(collected_fields, field_path)
            return float(value or 0) > threshold
    except Exception:
        pass

    # Default to including the document
    return True


def _get_nested_value(data: dict, path: str) -> Any:
    """Get a nested value from a dictionary using dot notation."""
    keys = path.split(".")
    value = data
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
    return value


def check_document_status(
    state: Dict[str, Any],
    product_line: Optional[str] = None,
    incident_type: Optional[str] = None,
) -> DocumentFlowStatus:
    """
    Check the current status of document collection.

    Args:
        state: The conversation state
        product_line: Optional override for product line
        incident_type: Optional override for incident type

    Returns:
        DocumentFlowStatus with current progress
    """
    product_line = product_line or state.get("product_line", "auto")
    collected_fields = state.get("collected_fields", {})
    incident_type = incident_type or collected_fields.get("incident_type")

    required_docs = get_required_documents(product_line, incident_type, collected_fields)
    uploaded_docs = {
        doc["doc_type"]: doc
        for doc in state.get("uploaded_documents", [])
    }
    verified_docs = state.get("verified_documents", {})

    # Find next required document
    next_required = None
    for doc_type in required_docs:
        if doc_type not in uploaded_docs:
            next_required = doc_type
            break

    # Calculate progress
    uploaded_count = sum(1 for dt in required_docs if dt in uploaded_docs)
    progress_pct = (uploaded_count / len(required_docs) * 100) if required_docs else 100

    return DocumentFlowStatus(
        required_documents=required_docs,
        uploaded_documents=uploaded_docs,
        verified_documents=verified_docs,
        current_document=next_required,
        all_required_present=next_required is None,
        next_required=next_required,
        progress_pct=progress_pct,
    )


def get_next_document_request(
    status: DocumentFlowStatus,
    required_docs: Optional[List[str]] = None,
) -> Optional[DocumentRequest]:
    """
    Get the next document request to send to the user.

    Args:
        status: Current document flow status
        required_docs: Optional list of required documents

    Returns:
        DocumentRequest with message, or None if all documents collected
    """
    required_docs = required_docs or status.required_documents

    if status.all_required_present:
        return None

    next_doc = status.next_required
    if not next_doc:
        return None

    message = DOCUMENT_REQUEST_MESSAGES.get(
        next_doc,
        f"Please upload your {next_doc.replace('_', ' ')} document."
    )

    # Add progress indicator
    uploaded_count = len(status.uploaded_documents)
    total_count = len(required_docs)
    progress_msg = f"\n\n(Document {uploaded_count + 1} of {total_count})"

    return DocumentRequest(
        doc_type=next_doc,
        request_message=message + progress_msg,
        is_required=True,
    )


def get_document_display_name(doc_type: str) -> str:
    """Get a user-friendly display name for a document type."""
    display_names = {
        "police_report": "Police Report",
        "incident_photos": "Incident Photos",
        "repair_estimate": "Repair Estimate",
        "invoice": "Invoice",
        "eob": "Explanation of Benefits",
        "medical_record": "Medical Records",
        "photo": "Photo",
        "other": "Document",
    }
    return display_names.get(doc_type, doc_type.replace("_", " ").title())
