"""
FNOL State Definition

Defines the state structure for the FNOL conversation flow.
This state is maintained throughout the claim intake process and
is persisted to the ClaimDraft database model.
"""
from typing import TypedDict, List, Optional, Annotated, Any
from datetime import datetime
import operator
import uuid


class PolicyMatchData(TypedDict, total=False):
    """Policy matching result."""
    status: str  # matched, guest, failed, pending
    policy_id: Optional[str]
    policy_number: Optional[str]
    method: Optional[str]  # policy_number, phone_lookup, name_dob
    confidence: float
    holder_name: Optional[str]
    vehicles: List[dict]
    drivers: List[dict]


class IncidentData(TypedDict, total=False):
    """Core incident information."""
    loss_type: Optional[str]
    loss_subtype: Optional[str]
    date: Optional[str]  # ISO date string
    time: Optional[str]  # HH:MM format
    time_approximate: bool
    location_raw: Optional[str]
    location_normalized: Optional[str]
    lat: Optional[float]
    lng: Optional[float]
    description: Optional[str]


class VehicleData(TypedDict, total=False):
    """Vehicle information."""
    vehicle_id: str
    role: str  # insured, third_party, unknown
    vin: Optional[str]
    year: Optional[int]
    make: Optional[str]
    model: Optional[str]
    color: Optional[str]
    license_plate: Optional[str]
    license_state: Optional[str]
    from_policy: bool
    policy_vehicle_id: Optional[str]
    drivable: Optional[str]  # yes, no, unknown
    current_location: Optional[str]
    tow_needed: bool
    is_rental: bool
    rental_company: Optional[str]


class PartyData(TypedDict, total=False):
    """Party (person) information."""
    party_id: str
    role: str  # insured_driver, third_party_driver, witness, etc.
    vehicle_id: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    dob: Optional[str]
    drivers_license: Optional[str]
    license_state: Optional[str]
    relationship_to_insured: Optional[str]
    has_permission: Optional[bool]
    insurance_carrier: Optional[str]
    insurance_policy_number: Optional[str]
    is_unknown: bool
    unknown_description: Optional[str]


class ImpactData(TypedDict, total=False):
    """Impact relationship between vehicles."""
    impact_id: str
    from_vehicle_id: Optional[str]
    to_vehicle_id: Optional[str]
    impact_type: Optional[str]
    from_unknown: bool
    to_unknown: bool
    description: Optional[str]


class InjuryData(TypedDict, total=False):
    """Injury information."""
    injury_id: str
    party_id: str
    severity: str  # none, unknown, minor, moderate, severe, fatal
    treatment_level: str  # none, onsite, urgent_care, er, admitted
    body_part: Optional[str]
    ambulance_called: bool
    hospitalized: bool
    hospital_name: Optional[str]


class DamageData(TypedDict, total=False):
    """Damage information."""
    damage_id: str
    vehicle_id: Optional[str]
    damage_type: str  # vehicle, property, personal_property
    damage_area: Optional[str]
    description: Optional[str]
    estimated_amount: Optional[float]
    pre_existing: bool
    property_type: Optional[str]
    property_owner_name: Optional[str]


class EvidenceData(TypedDict, total=False):
    """Evidence/document information."""
    evidence_id: str
    evidence_type: str
    subtype: Optional[str]
    description: Optional[str]
    upload_status: str  # pending, uploaded, verified, failed
    document_id: Optional[str]


class PoliceData(TypedDict, total=False):
    """Police involvement information."""
    contacted: Optional[str]  # yes, no, unknown, pending
    report_number: Optional[str]
    agency: Optional[str]
    officer_name: Optional[str]
    officer_badge: Optional[str]
    citation_issued: Optional[bool]
    dui_suspected: Optional[bool]


class TriageResult(TypedDict, total=False):
    """Triage decision result."""
    route: str  # stp, adjuster, siu_review, emergency
    score: int
    reasons: List[str]
    flags: List[str]
    rule_version: str


class UIHints(TypedDict, total=False):
    """Hints for frontend rendering."""
    input_type: str  # text, date, time, select, multiselect, yesno, photo, document
    options: List[dict]  # For select inputs
    placeholder: Optional[str]
    validation: dict
    show_progress: bool
    show_summary: bool
    allow_skip: bool


class FNOLConversationState(TypedDict):
    """
    Complete state for FNOL conversation flow.

    This state is:
    - Maintained throughout the conversation
    - Persisted to Redis for session management
    - Synced to ClaimDraft database model
    """
    # Session identification
    thread_id: str
    user_id: Optional[str]
    claim_draft_id: str

    # State machine position
    current_state: str  # One of 12 top-level states
    previous_state: Optional[str]
    state_step: str  # Sub-step within current state
    state_data: dict  # Temporary data for current state

    # State history for audit
    state_history: Annotated[List[dict], operator.add]

    # Conversation messages
    messages: Annotated[List[dict], operator.add]
    current_input: str
    ai_response: str

    # Scenario detection
    detected_scenarios: List[str]  # Playbook IDs detected
    active_playbooks: List[str]  # Currently active playbooks
    playbook_questions: List[dict]  # Additional questions from playbooks
    playbook_data: dict  # Data collected by playbooks

    # Collected data (mirrors ClaimDraft schema)
    policy_match: PolicyMatchData
    incident: IncidentData
    vehicles: List[VehicleData]
    parties: List[PartyData]
    impacts: List[ImpactData]
    injuries: List[InjuryData]
    damages: List[DamageData]
    evidence: List[EvidenceData]
    police: PoliceData

    # Safety check results
    safety_confirmed: bool
    emergency_detected: bool
    emergency_type: Optional[str]

    # Triage
    triage_result: Optional[TriageResult]

    # Consents
    consents: List[dict]
    fraud_acknowledgment: bool

    # Control flags
    needs_user_input: bool
    pending_question: Optional[str]
    pending_question_field: Optional[str]  # Which field we're collecting
    validation_errors: List[str]
    should_escalate: bool
    escalation_reason: Optional[str]
    is_complete: bool

    # UI hints for frontend
    ui_hints: UIHints

    # Progress tracking
    completed_states: List[str]
    progress_percent: int

    # Timestamps
    created_at: str
    updated_at: str


def create_initial_fnol_state(
    thread_id: str,
    user_id: Optional[str] = None,
    policy_id: Optional[str] = None,
) -> FNOLConversationState:
    """
    Create initial FNOL conversation state.

    Args:
        thread_id: Unique conversation thread identifier
        user_id: Optional user ID if authenticated
        policy_id: Optional policy ID if known

    Returns:
        Initial FNOLConversationState
    """
    now = datetime.utcnow().isoformat()
    claim_draft_id = str(uuid.uuid4())

    return FNOLConversationState(
        # Session
        thread_id=thread_id,
        user_id=user_id,
        claim_draft_id=claim_draft_id,

        # State machine
        current_state="SAFETY_CHECK",
        previous_state=None,
        state_step="initial",
        state_data={},
        state_history=[],

        # Conversation
        messages=[],
        current_input="",
        ai_response="",

        # Scenarios
        detected_scenarios=[],
        active_playbooks=[],
        playbook_questions=[],
        playbook_data={},

        # Collected data
        policy_match=PolicyMatchData(
            status="pending",
            policy_id=policy_id,
        ),
        incident=IncidentData(),
        vehicles=[],
        parties=[],
        impacts=[],
        injuries=[],
        damages=[],
        evidence=[],
        police=PoliceData(),

        # Safety
        safety_confirmed=False,
        emergency_detected=False,
        emergency_type=None,

        # Triage
        triage_result=None,

        # Consents
        consents=[],
        fraud_acknowledgment=False,

        # Control
        needs_user_input=True,
        pending_question=None,
        pending_question_field=None,
        validation_errors=[],
        should_escalate=False,
        escalation_reason=None,
        is_complete=False,

        # UI
        ui_hints=UIHints(
            input_type="text",
            show_progress=True,
            show_summary=False,
            allow_skip=False,
        ),

        # Progress
        completed_states=[],
        progress_percent=0,

        # Timestamps
        created_at=now,
        updated_at=now,
    )


# State transition map - defines valid transitions
STATE_TRANSITIONS = {
    "SAFETY_CHECK": ["IDENTITY_MATCH", "HANDOFF_ESCALATION"],
    "IDENTITY_MATCH": ["INCIDENT_CORE", "HANDOFF_ESCALATION"],
    "INCIDENT_CORE": ["LOSS_MODULE"],
    "LOSS_MODULE": ["VEHICLE_DRIVER"],
    "VEHICLE_DRIVER": ["THIRD_PARTIES"],
    "THIRD_PARTIES": ["INJURIES"],
    "INJURIES": ["DAMAGE_EVIDENCE", "HANDOFF_ESCALATION"],
    "DAMAGE_EVIDENCE": ["TRIAGE"],
    "TRIAGE": ["CLAIM_CREATE", "HANDOFF_ESCALATION"],
    "CLAIM_CREATE": ["NEXT_STEPS", "HANDOFF_ESCALATION"],
    "NEXT_STEPS": [],  # Terminal state
    "HANDOFF_ESCALATION": [],  # Terminal state
}


# States in order for progress tracking
STATE_ORDER = [
    "SAFETY_CHECK",
    "IDENTITY_MATCH",
    "INCIDENT_CORE",
    "LOSS_MODULE",
    "VEHICLE_DRIVER",
    "THIRD_PARTIES",
    "INJURIES",
    "DAMAGE_EVIDENCE",
    "TRIAGE",
    "CLAIM_CREATE",
    "NEXT_STEPS",
]


def calculate_progress(completed_states: List[str], current_state: str) -> int:
    """Calculate progress percentage based on completed states."""
    total_states = len(STATE_ORDER)
    if current_state == "HANDOFF_ESCALATION":
        # Escalation is a terminal state but not completion
        return int((len(completed_states) / total_states) * 100)

    try:
        current_index = STATE_ORDER.index(current_state)
        return int((current_index / total_states) * 100)
    except ValueError:
        return 0


def get_next_states(current_state: str) -> List[str]:
    """Get valid next states from current state."""
    return STATE_TRANSITIONS.get(current_state, [])
