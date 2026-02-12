"""
Base utilities for FNOL state handlers.

Provides common functions for:
- Parsing user input
- Updating state
- Generating responses
- Recording audit events
"""
from typing import Optional, List, Tuple
from datetime import datetime
import re

from app.orchestration.fnol.state import FNOLConversationState


def parse_yes_no(text: str) -> Optional[bool]:
    """
    Parse user input for yes/no responses.

    Args:
        text: User's input text

    Returns:
        True for yes, False for no, None if unclear
    """
    text_lower = text.lower().strip()

    yes_patterns = [
        r'^y(es)?$', r'^yeah?$', r'^yep$', r'^yup$', r'^sure$',
        r'^ok(ay)?$', r'^affirmative$', r'^correct$', r'^right$',
        r"^that'?s (right|correct)$", r'^i am$', r"^we('re| are)$",
        r'^safe$', r"^we'?re safe$", r'^i\'?m safe$', r'^all safe$',
    ]

    no_patterns = [
        r'^no?$', r'^nope$', r'^nah$', r'^negative$',
        r'^not (yet|now|really|safe)$', r'^i\'?m not$',
        r"^we('re| are) not$", r'^unsafe$', r'^help$',
        r'^need help$', r'^emergency$',
    ]

    for pattern in yes_patterns:
        if re.match(pattern, text_lower):
            return True

    for pattern in no_patterns:
        if re.match(pattern, text_lower):
            return False

    # Check for keywords
    if any(word in text_lower for word in ['yes', 'safe', 'okay', 'fine', 'good']):
        return True
    if any(word in text_lower for word in ['no', 'not safe', 'help', 'emergency', 'danger']):
        return False

    return None


def parse_injury_response(text: str) -> Tuple[Optional[bool], Optional[str]]:
    """
    Parse user input for injury-related questions.

    Args:
        text: User's input text

    Returns:
        Tuple of (has_injury: bool or None, severity_hint: str or None)
    """
    text_lower = text.lower().strip()

    # Check for emergency keywords first
    emergency_keywords = ['ambulance', 'hospital', 'unconscious', 'bleeding heavily',
                         'can\'t breathe', 'chest pain', 'dying', 'dead', 'fatal']
    for keyword in emergency_keywords:
        if keyword in text_lower:
            return True, 'severe'

    # Check for injury indicators
    injury_keywords = ['hurt', 'injured', 'pain', 'bleeding', 'broken', 'cut',
                       'bruise', 'whiplash', 'sore', 'ache']
    if any(keyword in text_lower for keyword in injury_keywords):
        return True, 'unknown'

    # Check for clear no
    no_injury_patterns = ['no one', 'nobody', 'no injuries', 'everyone is fine',
                         'all fine', 'we\'re okay', 'we\'re fine', 'not hurt',
                         'not injured', 'no', 'none']
    for pattern in no_injury_patterns:
        if pattern in text_lower:
            return False, None

    # Check for unsure
    unsure_patterns = ['not sure', 'don\'t know', 'maybe', 'might be', 'possibly',
                      'think so', 'could be']
    for pattern in unsure_patterns:
        if pattern in text_lower:
            return True, 'unknown'  # Treat unsure as positive for safety

    return None, None


def add_audit_event(
    state: FNOLConversationState,
    action: str,
    actor: str = "system",
    field_changed: Optional[str] = None,
    data_before: Optional[dict] = None,
    data_after: Optional[dict] = None,
    confidence: Optional[float] = None,
) -> FNOLConversationState:
    """
    Add an audit event to the state history.

    Args:
        state: Current conversation state
        action: Description of what happened
        actor: Who/what triggered this (user, system, llm:intent, etc.)
        field_changed: Which field was changed
        data_before: Previous value
        data_after: New value
        confidence: AI confidence if applicable

    Returns:
        Updated state with audit event
    """
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "state": state.get("current_state"),
        "step": state.get("state_step"),
        "action": action,
        "actor": actor,
        "field_changed": field_changed,
        "data_before": data_before,
        "data_after": data_after,
        "confidence": confidence,
        "user_input": state.get("current_input"),
    }

    state["state_history"] = state.get("state_history", []) + [event]
    return state


def transition_state(
    state: FNOLConversationState,
    new_state: str,
    new_step: str = "initial",
) -> FNOLConversationState:
    """
    Transition to a new state.

    Args:
        state: Current conversation state
        new_state: Target state name
        new_step: Initial step in new state

    Returns:
        Updated state
    """
    old_state = state.get("current_state")

    # Update completed states
    completed = state.get("completed_states", [])
    if old_state and old_state not in completed:
        completed = completed + [old_state]

    state["previous_state"] = old_state
    state["current_state"] = new_state
    state["state_step"] = new_step
    state["state_data"] = {}
    state["completed_states"] = completed

    # Add audit event
    state = add_audit_event(
        state,
        action=f"transition_to_{new_state}",
        actor="system",
        field_changed="current_state",
        data_before=old_state,
        data_after=new_state,
    )

    return state


def set_response(
    state: FNOLConversationState,
    response: str,
    pending_question: Optional[str] = None,
    pending_field: Optional[str] = None,
    input_type: str = "text",
    options: Optional[List[dict]] = None,
    allow_skip: bool = False,
    validation_errors: Optional[List[str]] = None,
) -> FNOLConversationState:
    """
    Set the AI response and UI hints.

    Args:
        state: Current conversation state
        response: The response message
        pending_question: Question identifier
        pending_field: Field being collected
        input_type: Type of input expected
        options: Options for select inputs
        allow_skip: Whether user can skip this question
        validation_errors: Any validation errors to display

    Returns:
        Updated state
    """
    state["ai_response"] = response
    state["pending_question"] = pending_question
    state["pending_question_field"] = pending_field
    state["needs_user_input"] = True
    state["validation_errors"] = validation_errors or []

    state["ui_hints"] = {
        "input_type": input_type,
        "options": options or [],
        "show_progress": True,
        "show_summary": state.get("current_state") not in ["SAFETY_CHECK", "IDENTITY_MATCH"],
        "allow_skip": allow_skip,
    }

    return state


def format_vehicle_display(vehicle: dict) -> str:
    """Format vehicle information for display."""
    parts = []
    if vehicle.get("year"):
        parts.append(str(vehicle["year"]))
    if vehicle.get("make"):
        parts.append(vehicle["make"])
    if vehicle.get("model"):
        parts.append(vehicle["model"])
    if vehicle.get("color"):
        parts.append(f"({vehicle['color']})")

    return " ".join(parts) if parts else "Vehicle"


def format_party_display(party: dict) -> str:
    """Format party information for display."""
    if party.get("is_unknown"):
        return "Unknown party"

    name_parts = []
    if party.get("first_name"):
        name_parts.append(party["first_name"])
    if party.get("last_name"):
        name_parts.append(party["last_name"])

    name = " ".join(name_parts) if name_parts else "Person"

    role = party.get("role", "").replace("_", " ").title()
    return f"{name} ({role})" if role else name
