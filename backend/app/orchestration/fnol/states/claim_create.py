"""
CLAIM_CREATE State Handler

Creates the claim in the database system:
- Generates claim draft record
- Persists all collected data
- Returns claim reference number
"""
from typing import Optional
from datetime import datetime
import uuid

from app.orchestration.fnol.state import FNOLConversationState
from app.orchestration.fnol.states.base import (
    add_audit_event,
    transition_state,
    set_response,
)


def claim_create_node(state: FNOLConversationState) -> FNOLConversationState:
    """Process the CLAIM_CREATE state."""
    step = state.get("state_step", "initial")

    # Step 1: Show summary and request confirmation
    if step == "initial":
        summary = generate_claim_summary(state)
        state["state_data"]["claim_summary"] = summary

        state["state_step"] = "awaiting_confirmation"
        return set_response(
            state,
            response=(
                "Please review your claim information:\n\n"
                f"{summary}\n\n"
                "Is all the information correct?"
            ),
            pending_question="confirm_claim",
            pending_field="claim_confirmed",
            input_type="yesno",
            options=[
                {"value": "yes", "label": "Yes, submit my claim"},
                {"value": "no", "label": "No, I need to make changes"},
            ],
        )

    # Step 2: Handle confirmation
    if step == "awaiting_confirmation":
        user_input = state.get("current_input", "").lower()

        if "no" in user_input or "change" in user_input or "edit" in user_input:
            state["state_step"] = "awaiting_edit_section"
            return set_response(
                state,
                response="What would you like to change?",
                pending_question="edit_section",
                pending_field="edit_request",
                input_type="select",
                options=[
                    {"value": "incident", "label": "Incident details"},
                    {"value": "vehicle", "label": "Vehicle information"},
                    {"value": "parties", "label": "Other parties"},
                    {"value": "injuries", "label": "Injury information"},
                    {"value": "damage", "label": "Damage details"},
                    {"value": "cancel", "label": "Cancel and start over"},
                ],
            )

        # User confirmed - create the claim
        claim_result = create_claim_draft(state)

        if claim_result.get("success"):
            state["claim_draft_id"] = claim_result["claim_draft_id"]
            state["claim_number"] = claim_result["claim_number"]

            state = add_audit_event(
                state,
                action="claim_created",
                actor="system",
                field_changed="claim_draft_id",
                data_after={
                    "claim_draft_id": claim_result["claim_draft_id"],
                    "claim_number": claim_result["claim_number"],
                },
            )

            state["state_step"] = "complete"
            return transition_state(state, "NEXT_STEPS", "initial")
        else:
            # Creation failed - offer to retry or escalate
            state["state_step"] = "creation_failed"
            return set_response(
                state,
                response=(
                    "I encountered an issue while submitting your claim. "
                    "Would you like me to try again, or would you prefer to speak with an agent?"
                ),
                pending_question="retry_or_agent",
                pending_field="creation_retry",
                input_type="select",
                options=[
                    {"value": "retry", "label": "Try again"},
                    {"value": "agent", "label": "Speak with an agent"},
                ],
            )

    # Step 3: Handle edit section selection
    if step == "awaiting_edit_section":
        user_input = state.get("current_input", "").lower()

        if "cancel" in user_input or "start over" in user_input:
            # User wants to start over - this would typically create a new session
            state["should_escalate"] = True
            state["escalation_reason"] = "User requested to start over"
            state["state_step"] = "complete"
            return set_response(
                state,
                response=(
                    "I understand you'd like to start over. "
                    "Please call back or refresh the page to begin a new claim."
                ),
                pending_question=None,
            )

        # Map edit request to state
        edit_state_map = {
            "incident": "INCIDENT_CORE",
            "vehicle": "VEHICLE_DRIVER",
            "parties": "THIRD_PARTIES",
            "injuries": "INJURIES",
            "damage": "DAMAGE_EVIDENCE",
        }

        for key, target_state in edit_state_map.items():
            if key in user_input:
                state = add_audit_event(
                    state,
                    action="edit_requested",
                    actor="user",
                    data_after={"section": key, "target_state": target_state},
                )
                # Set flag to indicate we're in edit mode
                state["state_data"]["editing"] = True
                state["state_data"]["return_to_state"] = "CLAIM_CREATE"
                return transition_state(state, target_state, "edit_mode")

        # Couldn't determine what to edit
        return set_response(
            state,
            response="I didn't understand which section you'd like to edit. Please select an option:",
            pending_question="edit_section",
            pending_field="edit_request",
            input_type="select",
            options=[
                {"value": "incident", "label": "Incident details"},
                {"value": "vehicle", "label": "Vehicle information"},
                {"value": "parties", "label": "Other parties"},
                {"value": "injuries", "label": "Injury information"},
                {"value": "damage", "label": "Damage details"},
                {"value": "cancel", "label": "Cancel changes"},
            ],
        )

    # Step 4: Handle creation failure retry
    if step == "creation_failed":
        user_input = state.get("current_input", "").lower()

        if "agent" in user_input:
            state["should_escalate"] = True
            state["escalation_reason"] = "Claim creation failed, user requested agent"
            state["state_step"] = "complete"
            return transition_state(state, "HANDOFF_ESCALATION", "technical_issue")

        # Retry claim creation
        claim_result = create_claim_draft(state)

        if claim_result.get("success"):
            state["claim_draft_id"] = claim_result["claim_draft_id"]
            state["claim_number"] = claim_result["claim_number"]
            state["state_step"] = "complete"
            return transition_state(state, "NEXT_STEPS", "initial")
        else:
            # Still failing - escalate
            state["should_escalate"] = True
            state["escalation_reason"] = "Claim creation failed after retry"
            state["state_step"] = "complete"
            return transition_state(state, "HANDOFF_ESCALATION", "technical_issue")

    # Default transition
    return transition_state(state, "NEXT_STEPS", "initial")


def generate_claim_summary(state: FNOLConversationState) -> str:
    """Generate a human-readable claim summary."""
    lines = []

    # Incident information
    incident = state.get("incident", {})
    if incident:
        lines.append("**Incident Details**")
        if incident.get("loss_type"):
            loss_type = incident["loss_type"].replace("_", " ").title()
            lines.append(f"• Type: {loss_type}")
        if incident.get("date"):
            lines.append(f"• Date: {incident['date']}")
        if incident.get("time"):
            lines.append(f"• Time: {incident['time']}")
        if incident.get("location_raw"):
            lines.append(f"• Location: {incident['location_raw']}")
        if incident.get("description"):
            desc = incident["description"][:200]
            if len(incident["description"]) > 200:
                desc += "..."
            lines.append(f"• Description: {desc}")
        lines.append("")

    # Vehicles
    vehicles = state.get("vehicles", [])
    if vehicles:
        lines.append("**Vehicles Involved**")
        for v in vehicles:
            parts = []
            if v.get("year"):
                parts.append(str(v["year"]))
            if v.get("make"):
                parts.append(v["make"])
            if v.get("model"):
                parts.append(v["model"])
            vehicle_str = " ".join(parts) if parts else "Vehicle"

            role = v.get("role", "").replace("_", " ").title()
            drivable = "Yes" if v.get("is_drivable") else "No"

            lines.append(f"• {vehicle_str} ({role})")
            lines.append(f"  Drivable: {drivable}")
        lines.append("")

    # Parties
    parties = state.get("parties", [])
    if parties:
        lines.append("**People Involved**")
        for p in parties:
            name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
            if not name:
                name = "Unknown"
            role = p.get("role", "").replace("_", " ").title()
            lines.append(f"• {name} ({role})")
        lines.append("")

    # Injuries
    injuries = state.get("injuries", [])
    injury_count = len([i for i in injuries if i.get("severity") not in [None, "none"]])
    lines.append("**Injuries**")
    if injury_count == 0:
        lines.append("• No injuries reported")
    else:
        lines.append(f"• {injury_count} person(s) reported injuries")
        for i in injuries:
            if i.get("severity") not in [None, "none"]:
                severity = i.get("severity", "").title()
                treatment = i.get("treatment_level", "").replace("_", " ").title()
                lines.append(f"  - Severity: {severity}, Treatment: {treatment}")
    lines.append("")

    # Damages
    damages = state.get("damages", [])
    if damages:
        lines.append("**Damage**")
        for d in damages:
            area = d.get("damage_area", "").replace("_", " ").title()
            if d.get("description"):
                lines.append(f"• {area}: {d['description'][:100]}")
            else:
                lines.append(f"• {area}")
            if d.get("estimated_amount"):
                lines.append(f"  Estimated: ${d['estimated_amount']:,}")
        lines.append("")

    # Triage result (simplified for user)
    triage = state.get("triage_result")
    if triage:
        route = triage.get("route", "")
        if route == "stp":
            lines.append("**Processing**")
            lines.append("• Your claim qualifies for expedited processing")
        elif route == "adjuster":
            lines.append("**Processing**")
            lines.append("• Your claim will be reviewed by an adjuster")

    return "\n".join(lines)


def create_claim_draft(state: FNOLConversationState) -> dict:
    """
    Create the claim draft in the database.

    In real implementation, this would:
    1. Create ClaimDraft record
    2. Create related records (vehicles, parties, injuries, etc.)
    3. Return the claim number

    For now, returns a simulated success response.
    """
    # Generate claim draft ID and number
    claim_draft_id = str(uuid.uuid4())
    claim_number = generate_claim_number(state)

    # In real implementation:
    # 1. Create ClaimDraft record with all collected data
    # 2. Create ClaimDraftVehicle records
    # 3. Create ClaimDraftParty records
    # 4. Create ClaimDraftInjury records
    # 5. Create ClaimDraftDamage records
    # 6. Create ClaimDraftEvidence records
    # 7. Create ClaimDraftAudit records for the submission

    return {
        "success": True,
        "claim_draft_id": claim_draft_id,
        "claim_number": claim_number,
    }


def generate_claim_number(state: FNOLConversationState) -> str:
    """
    Generate a human-readable claim number.

    Format: FNOL-YYYY-NNNNNN
    """
    year = datetime.utcnow().year
    # In real implementation, this would be a sequential number from the database
    sequence = uuid.uuid4().hex[:6].upper()
    return f"FNOL-{year}-{sequence}"
