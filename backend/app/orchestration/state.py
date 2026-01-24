"""
Shared state and types for LangGraph orchestration
"""
from typing import TypedDict, List, Optional, Annotated, Any
from enum import Enum
import operator


class ClaimIntent(str, Enum):
    FILE_CLAIM = "file_claim"
    CHECK_STATUS = "check_status"
    COVERAGE_QUESTION = "coverage_question"
    BILLING = "billing"
    HUMAN_REQUEST = "human_request"
    UNKNOWN = "unknown"


class ProductLine(str, Enum):
    AUTO = "auto"
    HOME = "home"
    MEDICAL = "medical"


class ConversationState(TypedDict):
    """Shared state across all graphs."""
    # Session info
    thread_id: str
    user_id: str
    policy_id: Optional[str]
    claim_id: Optional[str]
    
    # Conversation
    messages: Annotated[List[dict], operator.add]
    current_input: str
    
    # Intent and routing
    intent: Optional[str]
    product_line: Optional[str]
    
    # Data collection
    collected_fields: dict
    required_fields: List[str]
    missing_fields: List[str]
    
    # Processing
    calculation_result: Optional[dict]
    ai_response: str
    confidence: float
    
    # Escalation
    should_escalate: bool
    escalation_reason: Optional[str]
    case_packet: Optional[dict]

    # Admin-configured flow settings
    flow_settings: Optional[dict]

    # Agent trace for multi-step orchestration
    agent_trace: List[dict]
    
    # Control
    next_step: str
    is_complete: bool


def create_initial_state(
    thread_id: str,
    user_id: str,
    policy_id: Optional[str] = None,
) -> ConversationState:
    """Create initial conversation state."""
    return ConversationState(
        thread_id=thread_id,
        user_id=user_id,
        policy_id=policy_id,
        claim_id=None,
        messages=[],
        current_input="",
        intent=None,
        product_line=None,
        collected_fields={},
        required_fields=[],
        missing_fields=[],
        calculation_result=None,
        ai_response="",
        confidence=1.0,
        should_escalate=False,
        escalation_reason=None,
        case_packet=None,
        flow_settings=None,
        agent_trace=[],
        next_step="classify_intent",
        is_complete=False,
    )


# Required fields by intent and product line
REQUIRED_FIELDS = {
    "file_claim": {
        "auto": [
            "incident_date", "incident_location", "incident_description",
            "incident_type", "estimated_damage", "vehicle_info",
            "other_party_info", "police_report_number",
        ],
        "home": [
            "incident_date", "incident_type", "incident_location",
            "incident_description", "affected_areas", "estimated_damage",
        ],
        "medical": [
            "service_date", "provider_name", "provider_npi",
            "diagnosis_codes", "procedure_codes", "billed_amount",
        ],
    },
    "check_status": {
        "auto": ["claim_number"],
        "home": ["claim_number"],
        "medical": ["claim_number"],
    },
}


def get_required_fields(intent: str, product_line: str) -> List[str]:
    """Get required fields for intent and product line."""
    intent_fields = REQUIRED_FIELDS.get(intent, {})
    return intent_fields.get(product_line, [])
