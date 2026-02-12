"""
INJURIES State Handler

Collects injury information for all parties:
- Who is injured
- Severity level
- Treatment received/needed
- Emergency services involvement
"""
from typing import Optional
import uuid

from app.orchestration.fnol.state import FNOLConversationState, InjuryData
from app.orchestration.fnol.states.base import (
    add_audit_event,
    transition_state,
    set_response,
    format_party_display,
)


def injuries_node(state: FNOLConversationState) -> FNOLConversationState:
    """Process the INJURIES state."""
    step = state.get("state_step", "initial")
    user_input = state.get("current_input", "").strip()

    # Step 1: Initial - Ask about injuries
    if step == "initial":
        # Check if we already have injury info from safety check
        if state.get("state_data", {}).get("emergency_services_called"):
            state["state_step"] = "awaiting_injury_details"
            return set_response(
                state,
                response="You mentioned earlier that someone was injured. Who was injured?",
                pending_question="injured_party",
                pending_field="injury.who",
                input_type="select",
                options=_get_party_options(state),
            )

        state["state_step"] = "awaiting_any_injuries"
        return set_response(
            state,
            response="Were there any injuries as a result of this incident?",
            pending_question="any_injuries",
            pending_field="injuries.any",
            input_type="yesno",
            options=[
                {"value": "no", "label": "No, no one was injured"},
                {"value": "yes", "label": "Yes, someone was injured"},
                {"value": "unsure", "label": "I'm not sure"},
            ],
        )

    # Step 2: Handle any injuries response
    if step == "awaiting_any_injuries":
        has_injury = None
        user_lower = user_input.lower()

        if "no" in user_lower and "injury" not in user_lower:
            has_injury = False
        elif "yes" in user_lower or "injured" in user_lower or "hurt" in user_lower:
            has_injury = True
        elif "unsure" in user_lower or "not sure" in user_lower or "maybe" in user_lower:
            has_injury = True  # Treat unsure as positive for routing

        if has_injury is False:
            state["state_step"] = "no_injuries"
            state = add_audit_event(
                state,
                action="no_injuries_reported",
                actor="user",
            )
            state = transition_state(state, "DAMAGE_EVIDENCE", "initial")
            return state

        if has_injury is True:
            state["state_step"] = "awaiting_injury_details"
            return set_response(
                state,
                response="Who was injured?",
                pending_question="injured_party",
                pending_field="injury.who",
                input_type="select",
                options=_get_party_options(state),
            )

        # Unclear response
        return set_response(
            state,
            response="Were there any injuries from this incident?",
            pending_question="any_injuries",
            pending_field="injuries.any",
            input_type="yesno",
            options=[
                {"value": "no", "label": "No injuries"},
                {"value": "yes", "label": "Yes, injuries"},
            ],
        )

    # Step 3: Handle who was injured
    if step == "awaiting_injury_details":
        parties = state.get("parties", [])
        selected_party = None

        # Try to match to existing party
        user_lower = user_input.lower()
        if "me" in user_lower or "myself" in user_lower or "i was" in user_lower:
            # Find insured driver
            for party in parties:
                if party.get("role") == "insured_driver":
                    selected_party = party
                    break

        if not selected_party:
            # Try to match by name or role
            for party in parties:
                name = f"{party.get('first_name', '')} {party.get('last_name', '')}".lower()
                if name.strip() and name in user_lower:
                    selected_party = party
                    break
                if party.get("role", "").replace("_", " ") in user_lower:
                    selected_party = party
                    break

        # Create or use party for injury
        party_id = selected_party.get("party_id") if selected_party else str(uuid.uuid4())

        if not selected_party:
            # Create new party record if needed
            new_party = {
                "party_id": party_id,
                "role": "injured_party",
                "first_name": user_input if len(user_input.split()) == 1 else user_input.split()[0],
            }
            parties.append(new_party)
            state["parties"] = parties

        state["state_data"]["current_injury_party_id"] = party_id
        state["state_step"] = "awaiting_injury_severity"

        return set_response(
            state,
            response="How would you describe the severity of the injuries?",
            pending_question="injury_severity",
            pending_field="injury.severity",
            input_type="select",
            options=[
                {"value": "minor", "label": "Minor (no medical treatment needed)"},
                {"value": "moderate", "label": "Moderate (outpatient treatment)"},
                {"value": "severe", "label": "Severe (hospitalization required)"},
                {"value": "unknown", "label": "Unknown at this time"},
            ],
        )

    # Step 4: Handle injury severity
    if step == "awaiting_injury_severity":
        user_lower = user_input.lower()
        severity = "unknown"

        if "minor" in user_lower or "small" in user_lower or "slight" in user_lower:
            severity = "minor"
        elif "moderate" in user_lower or "outpatient" in user_lower:
            severity = "moderate"
        elif "severe" in user_lower or "serious" in user_lower or "hospital" in user_lower:
            severity = "severe"
        elif "fatal" in user_lower or "dead" in user_lower or "died" in user_lower:
            severity = "fatal"

        party_id = state.get("state_data", {}).get("current_injury_party_id")

        injury = InjuryData(
            injury_id=str(uuid.uuid4()),
            party_id=party_id,
            severity=severity,
        )

        injuries = state.get("injuries", [])
        injuries.append(injury)
        state["injuries"] = injuries
        state["state_data"]["current_injury_id"] = injury["injury_id"]

        state = add_audit_event(
            state,
            action="injury_recorded",
            actor="user",
            field_changed="injuries",
            data_after={"severity": severity},
        )

        # For severe/fatal, escalate
        if severity in ["severe", "fatal"]:
            state["should_escalate"] = True
            state["escalation_reason"] = f"{severity.title()} injury reported"
            state["state_step"] = "complete"
            state = transition_state(state, "HANDOFF_ESCALATION", "initial")
            return state

        state["state_step"] = "awaiting_treatment"
        return set_response(
            state,
            response="Was medical treatment received or is it planned?",
            pending_question="treatment",
            pending_field="injury.treatment",
            input_type="select",
            options=[
                {"value": "none", "label": "No treatment needed"},
                {"value": "onsite", "label": "First aid at scene"},
                {"value": "urgent_care", "label": "Urgent care/clinic visit"},
                {"value": "er", "label": "Emergency room visit"},
                {"value": "admitted", "label": "Hospital admission"},
            ],
        )

    # Step 5: Handle treatment level
    if step == "awaiting_treatment":
        user_lower = user_input.lower()
        treatment = "none"

        if "none" in user_lower or "no treatment" in user_lower:
            treatment = "none"
        elif "first aid" in user_lower or "onsite" in user_lower or "scene" in user_lower:
            treatment = "onsite"
        elif "urgent" in user_lower or "clinic" in user_lower:
            treatment = "urgent_care"
        elif "emergency" in user_lower or "er" in user_lower:
            treatment = "er"
        elif "hospital" in user_lower or "admitted" in user_lower:
            treatment = "admitted"

        injuries = state.get("injuries", [])
        current_id = state.get("state_data", {}).get("current_injury_id")

        for injury in injuries:
            if injury.get("injury_id") == current_id:
                injury["treatment_level"] = treatment
                break

        state["injuries"] = injuries
        state["state_step"] = "awaiting_ambulance"

        return set_response(
            state,
            response="Was an ambulance called?",
            pending_question="ambulance",
            pending_field="injury.ambulance",
            input_type="yesno",
        )

    # Step 6: Handle ambulance
    if step == "awaiting_ambulance":
        ambulance_called = "yes" in user_input.lower()

        injuries = state.get("injuries", [])
        current_id = state.get("state_data", {}).get("current_injury_id")

        for injury in injuries:
            if injury.get("injury_id") == current_id:
                injury["ambulance_called"] = ambulance_called
                break

        state["injuries"] = injuries
        state["state_step"] = "awaiting_more_injuries"

        return set_response(
            state,
            response="Was anyone else injured?",
            pending_question="more_injuries",
            pending_field="injuries.more",
            input_type="yesno",
        )

    # Step 7: Handle more injuries
    if step == "awaiting_more_injuries":
        more_injuries = "yes" in user_input.lower()

        if more_injuries:
            state["state_step"] = "awaiting_injury_details"
            return set_response(
                state,
                response="Who else was injured?",
                pending_question="injured_party",
                pending_field="injury.who",
                input_type="select",
                options=_get_party_options(state),
            )

        state["state_step"] = "complete"
        state = transition_state(state, "DAMAGE_EVIDENCE", "initial")
        return state

    # Default transition
    state = transition_state(state, "DAMAGE_EVIDENCE", "initial")
    return state


def _get_party_options(state: FNOLConversationState) -> list:
    """Get list of parties as options for injury selection."""
    parties = state.get("parties", [])
    options = [{"value": "myself", "label": "Myself"}]

    for party in parties:
        if party.get("role") != "insured_driver":
            name = format_party_display(party)
            options.append({
                "value": party.get("party_id"),
                "label": name,
            })

    options.append({"value": "other", "label": "Someone else"})
    return options
