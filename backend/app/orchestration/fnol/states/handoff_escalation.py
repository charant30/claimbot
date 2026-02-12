"""
HANDOFF_ESCALATION State Handler

Handles transfer to human agents for:
- Emergency situations
- SIU review flags
- Technical issues
- User requests for human assistance
- Complex scenarios beyond automation
"""
from typing import Optional, Dict, Any
from datetime import datetime
import uuid

from app.orchestration.fnol.state import FNOLConversationState
from app.orchestration.fnol.states.base import (
    add_audit_event,
    set_response,
)


# Escalation type configurations
ESCALATION_CONFIGS = {
    "emergency": {
        "priority": "critical",
        "queue": "emergency",
        "message": (
            "I understand this is an emergency situation. "
            "I'm connecting you with our emergency response team immediately.\n\n"
            "**If anyone needs immediate medical attention, please call 911.**\n\n"
            "A specialist will be with you shortly. Please stay on the line."
        ),
        "sla_minutes": 2,
    },
    "severe_injury": {
        "priority": "high",
        "queue": "injury_claims",
        "message": (
            "I'm sorry to hear about the injuries. I'm connecting you with "
            "a specialized claims representative who can assist you.\n\n"
            "They will help ensure you get the care and support you need.\n"
            "Please hold for just a moment."
        ),
        "sla_minutes": 5,
    },
    "siu_review": {
        "priority": "normal",
        "queue": "review",
        "message": (
            "Thank you for providing all that information. "
            "I need to connect you with a claims specialist who can "
            "complete the review of your claim.\n\n"
            "Please hold while I transfer you."
        ),
        "sla_minutes": 15,
    },
    "user_request": {
        "priority": "normal",
        "queue": "general",
        "message": (
            "No problem! I'll connect you with one of our claims representatives "
            "who can assist you further.\n\n"
            "Current wait time is approximately 5 minutes. "
            "Please hold while I transfer your call."
        ),
        "sla_minutes": 10,
    },
    "technical_issue": {
        "priority": "normal",
        "queue": "general",
        "message": (
            "I apologize for the technical difficulty. "
            "I'm connecting you with a representative who can help "
            "complete your claim.\n\n"
            "All the information you've provided has been saved."
        ),
        "sla_minutes": 10,
    },
    "complex_scenario": {
        "priority": "normal",
        "queue": "complex_claims",
        "message": (
            "Your situation involves some complexities that are best handled "
            "by one of our specialized claims adjusters.\n\n"
            "I'm transferring you now. All your information will be available "
            "to the adjuster."
        ),
        "sla_minutes": 15,
    },
    "fraud_suspected": {
        "priority": "high",
        "queue": "siu",
        "message": (
            "Thank you for your patience. I need to connect you with a "
            "specialized team member to complete your claim.\n\n"
            "Please hold while I transfer you."
        ),
        "sla_minutes": 5,
    },
    "policy_issue": {
        "priority": "normal",
        "queue": "policy_services",
        "message": (
            "I'm having trouble locating your policy information. "
            "Let me connect you with our policy services team who can help.\n\n"
            "Please hold for a moment."
        ),
        "sla_minutes": 10,
    },
}


def handoff_escalation_node(state: FNOLConversationState) -> FNOLConversationState:
    """Process the HANDOFF_ESCALATION state."""
    step = state.get("state_step", "initial")

    # Determine escalation type from state
    escalation_type = determine_escalation_type(state)
    config = ESCALATION_CONFIGS.get(escalation_type, ESCALATION_CONFIGS["user_request"])

    # Step 1: Initial - Create escalation ticket and show message
    if step in ["initial", "emergency", "severe_injury", "siu_review", "technical_issue"]:
        # Use step as escalation type if it's a known type
        if step in ESCALATION_CONFIGS:
            escalation_type = step
            config = ESCALATION_CONFIGS[step]

        # Create escalation record
        escalation_record = create_escalation_record(state, escalation_type, config)
        state["state_data"]["escalation_record"] = escalation_record

        state = add_audit_event(
            state,
            action="escalation_initiated",
            actor="system",
            data_after={
                "escalation_type": escalation_type,
                "escalation_id": escalation_record["escalation_id"],
                "queue": config["queue"],
                "priority": config["priority"],
            },
        )

        # For emergency, don't wait for response
        if escalation_type == "emergency":
            state["is_complete"] = True
            state["state_step"] = "transferred"
            return set_response(
                state,
                response=config["message"],
                pending_question=None,
            )

        state["state_step"] = "awaiting_hold_confirmation"
        return set_response(
            state,
            response=config["message"],
            pending_question="hold_confirmation",
            pending_field="will_hold",
            input_type="select",
            options=[
                {"value": "hold", "label": "I'll hold"},
                {"value": "callback", "label": "Please call me back"},
            ],
        )

    # Step 2: Handle hold/callback choice
    if step == "awaiting_hold_confirmation":
        user_input = state.get("current_input", "").lower()

        if "callback" in user_input or "call" in user_input:
            state["state_step"] = "awaiting_callback_number"
            return set_response(
                state,
                response=(
                    "We'll call you back as soon as a representative is available.\n\n"
                    "What's the best phone number to reach you?"
                ),
                pending_question="callback_number",
                pending_field="callback_phone",
                input_type="phone",
            )

        # User will hold
        state["state_step"] = "holding"
        state["state_data"]["hold_start"] = datetime.utcnow().isoformat()

        return set_response(
            state,
            response=(
                "Thank you for holding. A representative will be with you shortly.\n\n"
                "While you wait, you can review the information you've provided "
                "by scrolling up in this conversation.\n\n"
                "Your place in queue is being held."
            ),
            pending_question="still_holding",
            pending_field="hold_status",
            input_type="select",
            options=[
                {"value": "holding", "label": "Still holding"},
                {"value": "callback", "label": "Actually, call me back instead"},
            ],
        )

    # Step 3: Handle callback number
    if step == "awaiting_callback_number":
        user_input = state.get("current_input", "").strip()

        # Basic phone validation
        phone = parse_phone_number(user_input)
        if not phone:
            return set_response(
                state,
                response="Please provide a valid phone number where we can reach you.",
                pending_question="callback_number",
                pending_field="callback_phone",
                input_type="phone",
            )

        state["state_data"]["callback_phone"] = phone

        # Schedule callback
        callback_record = schedule_callback(state, phone)
        state["state_data"]["callback_record"] = callback_record

        state = add_audit_event(
            state,
            action="callback_scheduled",
            actor="system",
            data_after={
                "callback_phone": phone,
                "callback_id": callback_record["callback_id"],
            },
        )

        state["is_complete"] = True
        state["state_step"] = "callback_scheduled"

        return set_response(
            state,
            response=(
                f"Got it! We'll call you at {phone}.\n\n"
                f"**Expected callback time:** Within {callback_record['estimated_wait']} minutes\n"
                f"**Reference number:** {state.get('claim_draft_id', 'N/A')[:8].upper()}\n\n"
                "If you don't hear from us within that time, please call 1-800-CLAIMS.\n\n"
                "Thank you for your patience, and take care!"
            ),
            pending_question=None,
        )

    # Step 4: Handle holding status
    if step == "holding":
        user_input = state.get("current_input", "").lower()

        if "callback" in user_input:
            state["state_step"] = "awaiting_callback_number"
            return set_response(
                state,
                response="What's the best phone number to reach you?",
                pending_question="callback_number",
                pending_field="callback_phone",
                input_type="phone",
            )

        # Calculate hold time
        hold_start = state.get("state_data", {}).get("hold_start")
        hold_duration = "a few minutes"
        if hold_start:
            try:
                start = datetime.fromisoformat(hold_start)
                duration = (datetime.utcnow() - start).seconds // 60
                hold_duration = f"{duration} minutes" if duration > 0 else "less than a minute"
            except (ValueError, TypeError):
                pass

        return set_response(
            state,
            response=(
                f"Thank you for continuing to hold. You've been waiting {hold_duration}.\n\n"
                "A representative should be with you very soon. "
                "We appreciate your patience!"
            ),
            pending_question="still_holding",
            pending_field="hold_status",
            input_type="select",
            options=[
                {"value": "holding", "label": "I'll keep holding"},
                {"value": "callback", "label": "Call me back instead"},
            ],
        )

    # Default - mark as complete
    state["is_complete"] = True
    state["state_step"] = "transferred"
    return state


def determine_escalation_type(state: FNOLConversationState) -> str:
    """Determine the appropriate escalation type based on state."""
    # Check for emergency indicators
    if state.get("emergency_detected"):
        return "emergency"

    if state.get("emergency_type") == "severe_injury":
        return "severe_injury"

    # Check triage result
    triage = state.get("triage_result", {})
    if triage.get("route") == "siu_review":
        return "siu_review"

    if triage.get("route") == "emergency":
        return "emergency"

    # Check escalation reason
    reason = state.get("escalation_reason", "").lower()

    if "fraud" in reason or "suspicious" in reason:
        return "fraud_suspected"

    if "technical" in reason or "failed" in reason or "error" in reason:
        return "technical_issue"

    if "policy" in reason or "coverage" in reason:
        return "policy_issue"

    if "complex" in reason or "complicated" in reason:
        return "complex_scenario"

    if "user request" in reason or "human" in reason:
        return "user_request"

    # Default
    return "user_request"


def create_escalation_record(
    state: FNOLConversationState,
    escalation_type: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Create an escalation record for the handoff."""
    escalation_id = str(uuid.uuid4())

    # Build context summary for agent
    context = build_agent_context(state)

    return {
        "escalation_id": escalation_id,
        "type": escalation_type,
        "queue": config["queue"],
        "priority": config["priority"],
        "sla_minutes": config["sla_minutes"],
        "created_at": datetime.utcnow().isoformat(),
        "claim_draft_id": state.get("claim_draft_id"),
        "thread_id": state.get("thread_id"),
        "context": context,
        "status": "pending",
    }


def build_agent_context(state: FNOLConversationState) -> Dict[str, Any]:
    """Build a context summary for the receiving agent."""
    context = {
        "conversation_length": len(state.get("messages", [])),
        "states_completed": state.get("completed_states", []),
        "current_state": state.get("current_state"),
        "escalation_reason": state.get("escalation_reason"),
    }

    # Policy info
    policy = state.get("policy_match", {})
    if policy:
        context["policy"] = {
            "status": policy.get("status"),
            "policy_number": policy.get("policy_number"),
            "holder_name": f"{policy.get('holder_first_name', '')} {policy.get('holder_last_name', '')}".strip(),
        }

    # Incident summary
    incident = state.get("incident", {})
    if incident:
        context["incident"] = {
            "loss_type": incident.get("loss_type"),
            "date": incident.get("date"),
            "location": incident.get("location_raw"),
        }

    # Key flags
    flags = []

    injuries = state.get("injuries", [])
    if any(i.get("severity") in ["severe", "fatal"] for i in injuries):
        flags.append("severe_injury")
    elif any(i.get("severity") not in [None, "none"] for i in injuries):
        flags.append("injuries_reported")

    vehicles = state.get("vehicles", [])
    if any(not v.get("is_drivable") for v in vehicles):
        flags.append("vehicle_not_drivable")

    if len(vehicles) > 2:
        flags.append("multi_vehicle")

    if "hit_and_run" in state.get("active_playbooks", []):
        flags.append("hit_and_run")

    triage = state.get("triage_result", {})
    if triage.get("flags"):
        flags.extend(triage["flags"][:5])  # Include top 5 triage flags

    context["flags"] = list(set(flags))  # Dedupe

    return context


def schedule_callback(state: FNOLConversationState, phone: str) -> Dict[str, Any]:
    """Schedule a callback for the user."""
    callback_id = str(uuid.uuid4())

    # Estimate wait based on escalation type
    escalation_record = state.get("state_data", {}).get("escalation_record", {})
    sla = escalation_record.get("sla_minutes", 15)

    return {
        "callback_id": callback_id,
        "phone": phone,
        "scheduled_at": datetime.utcnow().isoformat(),
        "estimated_wait": sla,
        "queue": escalation_record.get("queue", "general"),
        "priority": escalation_record.get("priority", "normal"),
        "status": "scheduled",
    }


def parse_phone_number(text: str) -> Optional[str]:
    """Parse and validate a phone number from user input."""
    import re

    # Remove common formatting
    digits = re.sub(r"[^\d]", "", text)

    # Check for valid US phone number (10 or 11 digits)
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"

    return None
