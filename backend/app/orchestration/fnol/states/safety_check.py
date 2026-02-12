"""
SAFETY_CHECK State Handler

This is the first state in the FNOL flow. It ensures:
1. The caller is in a safe location
2. No one needs immediate emergency assistance
3. Emergency services have been contacted if needed

If emergency is detected, routes to HANDOFF_ESCALATION.
Otherwise, proceeds to IDENTITY_MATCH.
"""
from typing import Dict, Any
from datetime import datetime

from app.orchestration.fnol.state import FNOLConversationState
from app.orchestration.fnol.states.base import (
    parse_yes_no,
    parse_injury_response,
    add_audit_event,
    transition_state,
    set_response,
)


def safety_check_node(state: FNOLConversationState) -> FNOLConversationState:
    """
    Process the SAFETY_CHECK state.

    Questions flow:
    1. "Are you currently in a safe location?"
    2. "Is anyone injured and needs immediate medical attention?"
    3. "Have emergency services been called?" (if injury detected)

    Args:
        state: Current conversation state

    Returns:
        Updated conversation state
    """
    step = state.get("state_step", "initial")
    user_input = state.get("current_input", "").strip()

    # Step 1: Initial - Ask about safety
    if step == "initial":
        # This is handled by the session creation
        # Just move to awaiting response
        state["state_step"] = "awaiting_safety"
        return state

    # Step 2: Process safety confirmation
    if step == "awaiting_safety":
        is_safe = parse_yes_no(user_input)

        if is_safe is None:
            # Unclear response, ask again
            return set_response(
                state,
                response="I want to make sure you're safe. Are you and everyone involved currently in a safe location, away from traffic?",
                pending_question="safety_confirmation",
                pending_field="safety_confirmed",
                input_type="yesno",
                options=[
                    {"value": "yes", "label": "Yes, we're safe"},
                    {"value": "no", "label": "No, I need help"},
                ],
            )

        if is_safe:
            # User is safe, ask about injuries
            state["safety_confirmed"] = True
            state["state_step"] = "awaiting_injury_check"

            state = add_audit_event(
                state,
                action="safety_confirmed",
                actor="user",
                field_changed="safety_confirmed",
                data_after=True,
            )

            return set_response(
                state,
                response="Good to hear you're safe. Is anyone injured or in need of immediate medical attention?",
                pending_question="injury_check",
                pending_field="emergency_detected",
                input_type="yesno",
                options=[
                    {"value": "no", "label": "No, no one is injured"},
                    {"value": "yes", "label": "Yes, someone is injured"},
                    {"value": "unsure", "label": "I'm not sure"},
                ],
            )
        else:
            # User is not safe
            state["state_step"] = "unsafe_guidance"
            return set_response(
                state,
                response=(
                    "Your safety is the priority. Please:\n\n"
                    "1. If you're in immediate danger, call 911\n"
                    "2. Move to a safe location away from traffic\n"
                    "3. Turn on your hazard lights if your vehicle is on the road\n\n"
                    "Once you're in a safe place, let me know and we can continue."
                ),
                pending_question="safety_retry",
                pending_field="safety_confirmed",
                input_type="yesno",
                options=[
                    {"value": "yes", "label": "I'm now in a safe location"},
                    {"value": "help", "label": "I need emergency assistance"},
                ],
            )

    # Step 3: Handle unsafe guidance response
    if step == "unsafe_guidance":
        is_safe = parse_yes_no(user_input)

        # Check for emergency keywords
        emergency_keywords = ['help', 'emergency', 'ambulance', '911', 'danger', 'stuck']
        needs_emergency = any(kw in user_input.lower() for kw in emergency_keywords)

        if needs_emergency:
            state["emergency_detected"] = True
            state["emergency_type"] = "caller_unsafe"
            state["should_escalate"] = True
            state["escalation_reason"] = "Caller reported being in unsafe situation"
            state["state_step"] = "complete"

            state = add_audit_event(
                state,
                action="emergency_detected",
                actor="system",
                field_changed="emergency_detected",
                data_after=True,
            )

            return set_response(
                state,
                response=(
                    "I'm connecting you with emergency assistance right away. "
                    "Please stay on the line.\n\n"
                    "If you haven't already, please call 911 for immediate help."
                ),
                pending_question=None,
            )

        if is_safe:
            state["safety_confirmed"] = True
            state["state_step"] = "awaiting_injury_check"

            return set_response(
                state,
                response="Good to hear you're now safe. Is anyone injured or in need of immediate medical attention?",
                pending_question="injury_check",
                pending_field="emergency_detected",
                input_type="yesno",
                options=[
                    {"value": "no", "label": "No, no one is injured"},
                    {"value": "yes", "label": "Yes, someone is injured"},
                    {"value": "unsure", "label": "I'm not sure"},
                ],
            )

        # Still not safe
        return set_response(
            state,
            response=(
                "Please focus on getting to safety first. If you need emergency services, call 911.\n\n"
                "Let me know when you're in a safe location."
            ),
            pending_question="safety_retry",
            pending_field="safety_confirmed",
            input_type="yesno",
            options=[
                {"value": "yes", "label": "I'm now safe"},
                {"value": "help", "label": "I need emergency assistance"},
            ],
        )

    # Step 4: Process injury check
    if step == "awaiting_injury_check":
        has_injury, severity = parse_injury_response(user_input)

        # Check for explicit "unsure" response
        if "unsure" in user_input.lower() or "not sure" in user_input.lower():
            has_injury = True
            severity = "unknown"

        if has_injury is None:
            # Unclear, default to asking for clarification
            return set_response(
                state,
                response="I want to make sure everyone is okay. Is anyone hurt or feeling unwell after the incident?",
                pending_question="injury_check",
                pending_field="emergency_detected",
                input_type="yesno",
                options=[
                    {"value": "no", "label": "No, everyone is okay"},
                    {"value": "yes", "label": "Yes, someone may be hurt"},
                ],
            )

        if has_injury:
            # Injury reported - check severity
            state["state_step"] = "awaiting_emergency_services"

            state = add_audit_event(
                state,
                action="injury_reported",
                actor="user",
                data_after={"has_injury": True, "severity_hint": severity},
            )

            if severity == "severe":
                # Severe injury - immediate escalation
                state["emergency_detected"] = True
                state["emergency_type"] = "severe_injury"
                state["should_escalate"] = True
                state["escalation_reason"] = "Severe injury reported"

                return set_response(
                    state,
                    response=(
                        "I understand this is a serious situation. "
                        "If you haven't already, please call 911 immediately.\n\n"
                        "I'm connecting you with our emergency response team right now."
                    ),
                    pending_question=None,
                )

            # Non-severe injury - ask about emergency services
            return set_response(
                state,
                response=(
                    "I'm sorry to hear that. Have emergency services (ambulance or police) been called?"
                ),
                pending_question="emergency_services",
                pending_field="emergency_services_called",
                input_type="yesno",
                options=[
                    {"value": "yes", "label": "Yes, they've been called"},
                    {"value": "no", "label": "No, not yet"},
                    {"value": "not_needed", "label": "It's minor, no ambulance needed"},
                ],
            )

        # No injury - proceed to identity match
        state["state_step"] = "complete"
        state = transition_state(state, "IDENTITY_MATCH", "initial")

        # Return without setting response - let identity_match handle it
        return state

    # Step 5: Process emergency services check
    if step == "awaiting_emergency_services":
        response_lower = user_input.lower()

        # Check if emergency services called
        services_called = any(word in response_lower for word in ['yes', 'called', 'way', 'coming', 'here'])
        not_needed = any(phrase in response_lower for phrase in ['minor', 'not needed', "don't need", 'small', 'okay'])

        if not_needed:
            # Minor injury, no emergency services needed
            state["state_step"] = "complete"

            state = add_audit_event(
                state,
                action="injury_minor_no_emergency",
                actor="user",
            )

            state = transition_state(state, "IDENTITY_MATCH", "initial")
            return state

        if services_called:
            # Emergency services on way - note and continue
            state["state_step"] = "complete"

            state = add_audit_event(
                state,
                action="emergency_services_contacted",
                actor="user",
            )

            # Store this info
            state["state_data"]["emergency_services_called"] = True

            state = transition_state(state, "IDENTITY_MATCH", "initial")
            return state

        # Not called yet - provide guidance
        state["state_step"] = "emergency_guidance"
        return set_response(
            state,
            response=(
                "If anyone needs medical attention, please call 911 or have someone drive them to the nearest hospital.\n\n"
                "Would you like to continue filing this claim now, or would you prefer to call back later once everyone is taken care of?"
            ),
            pending_question="continue_or_later",
            pending_field="continue_claim",
            input_type="select",
            options=[
                {"value": "continue", "label": "Continue now"},
                {"value": "later", "label": "I'll call back later"},
            ],
        )

    # Step 6: Handle emergency guidance response
    if step == "emergency_guidance":
        wants_to_continue = "continue" in user_input.lower() or "now" in user_input.lower()

        if wants_to_continue:
            state["state_step"] = "complete"
            state = transition_state(state, "IDENTITY_MATCH", "initial")
            return state

        # User wants to call back later
        state["should_escalate"] = False
        state["is_complete"] = True

        return set_response(
            state,
            response=(
                "That's completely understandable. Please take care of what's important first.\n\n"
                "You can return to file your claim at any time. Your reference number is: "
                f"{state.get('claim_draft_id', 'N/A')[:8].upper()}\n\n"
                "I hope everyone feels better soon."
            ),
            pending_question=None,
        )

    # Default: transition to next state
    state = transition_state(state, "IDENTITY_MATCH", "initial")
    return state
