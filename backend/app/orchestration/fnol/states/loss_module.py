"""
LOSS_MODULE State Handler

Detects applicable scenario playbooks based on incident data
and activates them for the rest of the flow.
"""
from typing import List
from app.orchestration.fnol.state import FNOLConversationState
from app.orchestration.fnol.states.base import (
    add_audit_event,
    transition_state,
    set_response,
)


# Scenario detection rules
SCENARIO_RULES = {
    "collision_two_vehicle": {
        "conditions": {"loss_type": "collision", "loss_subtype": "two_vehicle"},
        "priority": 1,
    },
    "collision_single_vehicle": {
        "conditions": {"loss_type": "collision", "loss_subtype": "single_vehicle"},
        "priority": 1,
    },
    "collision_multi_vehicle": {
        "conditions": {"loss_type": "collision", "loss_subtype": "multi_vehicle"},
        "priority": 1,
    },
    "hit_and_run": {
        "conditions": {"loss_type": "collision", "loss_subtype": "hit_and_run"},
        "priority": 2,
    },
    "weather_hail": {
        "conditions": {"loss_type": "weather", "loss_subtype": "hail"},
        "priority": 1,
    },
    "weather_flood": {
        "conditions": {"loss_type": "weather", "loss_subtype": "flood"},
        "priority": 1,
    },
    "weather_wind_tree": {
        "conditions": {"loss_type": "weather", "loss_subtype": ["wind", "tree"]},
        "priority": 1,
    },
    "theft_vehicle": {
        "conditions": {"loss_type": "theft", "loss_subtype": "vehicle_stolen"},
        "priority": 1,
    },
    "theft_attempted": {
        "conditions": {"loss_type": "theft", "loss_subtype": "attempted_theft"},
        "priority": 1,
    },
    "vandalism": {
        "conditions": {"loss_type": "vandalism"},
        "priority": 1,
    },
    "glass_only": {
        "conditions": {"loss_type": "glass"},
        "priority": 1,
    },
    "fire": {
        "conditions": {"loss_type": "fire"},
        "priority": 1,
    },
}


def loss_module_node(state: FNOLConversationState) -> FNOLConversationState:
    """
    Process the LOSS_MODULE state.

    Detects and activates scenario playbooks based on incident data.

    Args:
        state: Current conversation state

    Returns:
        Updated conversation state
    """
    step = state.get("state_step", "initial")
    incident = state.get("incident", {})

    if step == "initial":
        # Detect applicable scenarios
        detected = detect_scenarios(incident, state.get("state_data", {}))
        state["detected_scenarios"] = detected
        state["active_playbooks"] = detected

        # Set primary scenario
        if detected:
            state["incident"]["loss_subtype"] = state["incident"].get("loss_subtype") or detected[0]

        state = add_audit_event(
            state,
            action="scenarios_detected",
            actor="system",
            field_changed="detected_scenarios",
            data_after=detected,
        )

        # Generate summary of what we've collected
        loss_type = incident.get("loss_type", "incident")
        incident_date = incident.get("date", "unknown date")
        location = incident.get("location_raw", "unknown location")

        summary = f"I understand you're reporting a **{format_loss_type(loss_type)}** that occurred on **{incident_date}** at **{location}**."

        if detected:
            scenario_names = [format_scenario_name(s) for s in detected[:2]]
            summary += f"\n\nI'll guide you through the {', '.join(scenario_names)} claim process."

        state["state_step"] = "confirm_understanding"
        return set_response(
            state,
            response=summary + "\n\nIs this correct?",
            pending_question="confirm_incident",
            pending_field="incident_confirmed",
            input_type="yesno",
            options=[
                {"value": "yes", "label": "Yes, that's correct"},
                {"value": "no", "label": "No, let me clarify"},
            ],
        )

    if step == "confirm_understanding":
        user_input = state.get("current_input", "").lower()

        if "no" in user_input or "incorrect" in user_input or "wrong" in user_input:
            # Go back to incident core to correct
            state = transition_state(state, "INCIDENT_CORE", "initial")
            return state

        # Confirmed - proceed to vehicle/driver collection
        state["state_step"] = "complete"
        state = transition_state(state, "VEHICLE_DRIVER", "initial")
        return state

    # Default transition
    state = transition_state(state, "VEHICLE_DRIVER", "initial")
    return state


def detect_scenarios(incident: dict, state_data: dict) -> List[str]:
    """Detect applicable scenarios from incident data."""
    detected = []
    loss_type = incident.get("loss_type")
    loss_subtype = incident.get("loss_subtype")

    for scenario_id, rule in SCENARIO_RULES.items():
        conditions = rule["conditions"]

        # Check loss_type
        if "loss_type" in conditions:
            if conditions["loss_type"] != loss_type:
                continue

        # Check loss_subtype
        if "loss_subtype" in conditions:
            expected = conditions["loss_subtype"]
            if isinstance(expected, list):
                if loss_subtype not in expected:
                    continue
            elif expected != loss_subtype:
                continue

        detected.append(scenario_id)

    # Sort by priority
    detected.sort(key=lambda x: SCENARIO_RULES.get(x, {}).get("priority", 99))

    # Add secondary scenarios based on description keywords
    description = incident.get("description", "").lower()

    # Detect injury scenario
    injury_keywords = ["hurt", "injured", "pain", "hospital", "ambulance"]
    if any(kw in description for kw in injury_keywords):
        if "injury" not in detected:
            detected.append("injury")

    # Detect towing needed
    tow_keywords = ["tow", "can't drive", "not drivable", "won't start", "totaled"]
    if any(kw in description for kw in tow_keywords):
        if "towing" not in detected:
            detected.append("towing")

    # Detect police involvement
    police_keywords = ["police", "officer", "911", "report", "citation", "ticket"]
    if any(kw in description for kw in police_keywords):
        if "police_involved" not in detected:
            detected.append("police_involved")

    return detected


def format_loss_type(loss_type: str) -> str:
    """Format loss type for display."""
    mappings = {
        "collision": "vehicle collision",
        "theft": "theft",
        "weather": "weather-related damage",
        "vandalism": "vandalism",
        "glass": "glass damage",
        "fire": "vehicle fire",
        "other": "incident",
    }
    return mappings.get(loss_type, loss_type)


def format_scenario_name(scenario_id: str) -> str:
    """Format scenario ID for display."""
    mappings = {
        "collision_two_vehicle": "two-vehicle collision",
        "collision_single_vehicle": "single-vehicle accident",
        "collision_multi_vehicle": "multi-vehicle accident",
        "hit_and_run": "hit-and-run",
        "weather_hail": "hail damage",
        "weather_flood": "flood damage",
        "weather_wind_tree": "wind/tree damage",
        "theft_vehicle": "vehicle theft",
        "theft_attempted": "attempted theft",
        "vandalism": "vandalism",
        "glass_only": "glass",
        "fire": "fire damage",
        "injury": "injury",
        "towing": "towing",
        "police_involved": "police report",
    }
    return mappings.get(scenario_id, scenario_id.replace("_", " "))
