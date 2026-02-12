"""
VEHICLE_DRIVER State Handler

Collects information about the insured vehicle and driver:
1. Select vehicle from policy or enter manually
2. Confirm driver details
3. Capture drivable status and current location
"""
from typing import Optional
import uuid

from app.orchestration.fnol.state import FNOLConversationState, VehicleData, PartyData
from app.orchestration.fnol.states.base import (
    add_audit_event,
    transition_state,
    set_response,
    format_vehicle_display,
)


def vehicle_driver_node(state: FNOLConversationState) -> FNOLConversationState:
    """
    Process the VEHICLE_DRIVER state.

    Args:
        state: Current conversation state

    Returns:
        Updated conversation state
    """
    step = state.get("state_step", "initial")
    user_input = state.get("current_input", "").strip()
    policy_match = state.get("policy_match", {})

    # Step 1: Initial - Check if we have policy vehicles
    if step == "initial":
        policy_vehicles = policy_match.get("vehicles", [])

        if policy_vehicles:
            # Show vehicles from policy for selection
            options = []
            for i, v in enumerate(policy_vehicles):
                display = format_vehicle_display(v)
                options.append({
                    "value": str(i),
                    "label": display,
                    "data": v,
                })
            options.append({"value": "other", "label": "Different vehicle"})

            state["state_step"] = "awaiting_vehicle_selection"
            state["state_data"]["policy_vehicles"] = policy_vehicles

            return set_response(
                state,
                response="Which vehicle was involved in the incident?",
                pending_question="vehicle_selection",
                pending_field="vehicle",
                input_type="select",
                options=options,
            )
        else:
            # No policy vehicles, ask for vehicle info
            state["state_step"] = "awaiting_vehicle_year"
            return set_response(
                state,
                response="Let me get some information about the vehicle involved.\n\nWhat year is your vehicle?",
                pending_question="vehicle_year",
                pending_field="vehicle.year",
                input_type="text",
            )

    # Step 2: Handle vehicle selection from policy
    if step == "awaiting_vehicle_selection":
        policy_vehicles = state.get("state_data", {}).get("policy_vehicles", [])

        if "other" in user_input.lower() or "different" in user_input.lower():
            state["state_step"] = "awaiting_vehicle_year"
            return set_response(
                state,
                response="What year is the vehicle?",
                pending_question="vehicle_year",
                pending_field="vehicle.year",
                input_type="text",
            )

        # Try to match selection
        try:
            index = int(user_input.strip())
            if 0 <= index < len(policy_vehicles):
                selected = policy_vehicles[index]
                vehicle = VehicleData(
                    vehicle_id=str(uuid.uuid4()),
                    role="insured",
                    vin=selected.get("vin"),
                    year=selected.get("year"),
                    make=selected.get("make"),
                    model=selected.get("model"),
                    color=selected.get("color"),
                    license_plate=selected.get("license_plate"),
                    license_state=selected.get("license_state"),
                    from_policy=True,
                    policy_vehicle_id=selected.get("vehicle_id"),
                )
                state["vehicles"] = [vehicle]

                state = add_audit_event(
                    state,
                    action="vehicle_selected_from_policy",
                    actor="user",
                    field_changed="vehicles",
                    data_after=format_vehicle_display(selected),
                )

                state["state_step"] = "awaiting_drivable"
                return set_response(
                    state,
                    response=f"Got it - your **{format_vehicle_display(selected)}**.\n\nIs the vehicle drivable?",
                    pending_question="vehicle_drivable",
                    pending_field="vehicle.drivable",
                    input_type="select",
                    options=[
                        {"value": "yes", "label": "Yes, it's drivable"},
                        {"value": "no", "label": "No, it can't be driven"},
                        {"value": "unknown", "label": "I'm not sure"},
                    ],
                )
        except (ValueError, IndexError):
            pass

        # Invalid selection, ask again
        return set_response(
            state,
            response="Please select a vehicle from the list.",
            pending_question="vehicle_selection",
            pending_field="vehicle",
            input_type="select",
            options=state.get("ui_hints", {}).get("options", []),
        )

    # Step 3: Manual vehicle entry - year
    if step == "awaiting_vehicle_year":
        year = extract_year(user_input)
        if not year:
            return set_response(
                state,
                response="Please enter a valid year (e.g., 2022).",
                pending_question="vehicle_year",
                pending_field="vehicle.year",
                input_type="text",
                validation_errors=["Invalid year"],
            )

        state["state_data"]["vehicle_year"] = year
        state["state_step"] = "awaiting_vehicle_make"
        return set_response(
            state,
            response="What is the make of the vehicle (e.g., Honda, Toyota, Ford)?",
            pending_question="vehicle_make",
            pending_field="vehicle.make",
            input_type="text",
        )

    # Step 4: Manual vehicle entry - make
    if step == "awaiting_vehicle_make":
        if len(user_input) < 2:
            return set_response(
                state,
                response="Please enter the vehicle make.",
                pending_question="vehicle_make",
                pending_field="vehicle.make",
                input_type="text",
            )

        state["state_data"]["vehicle_make"] = user_input.title()
        state["state_step"] = "awaiting_vehicle_model"
        return set_response(
            state,
            response="What is the model (e.g., Accord, Camry, F-150)?",
            pending_question="vehicle_model",
            pending_field="vehicle.model",
            input_type="text",
        )

    # Step 5: Manual vehicle entry - model
    if step == "awaiting_vehicle_model":
        if len(user_input) < 1:
            return set_response(
                state,
                response="Please enter the vehicle model.",
                pending_question="vehicle_model",
                pending_field="vehicle.model",
                input_type="text",
            )

        # Create vehicle record
        vehicle = VehicleData(
            vehicle_id=str(uuid.uuid4()),
            role="insured",
            year=state.get("state_data", {}).get("vehicle_year"),
            make=state.get("state_data", {}).get("vehicle_make"),
            model=user_input.title(),
            from_policy=False,
        )
        state["vehicles"] = [vehicle]

        state["state_step"] = "awaiting_drivable"
        return set_response(
            state,
            response="Is the vehicle drivable?",
            pending_question="vehicle_drivable",
            pending_field="vehicle.drivable",
            input_type="select",
            options=[
                {"value": "yes", "label": "Yes, it's drivable"},
                {"value": "no", "label": "No, it can't be driven"},
                {"value": "unknown", "label": "I'm not sure"},
            ],
        )

    # Step 6: Handle drivable status
    if step == "awaiting_drivable":
        vehicles = state.get("vehicles", [])
        if vehicles:
            drivable = "unknown"
            if "yes" in user_input.lower() or "drivable" in user_input.lower():
                drivable = "yes"
            elif "no" in user_input.lower() or "can't" in user_input.lower():
                drivable = "no"

            vehicles[0]["drivable"] = drivable
            state["vehicles"] = vehicles

            if drivable == "no":
                state["state_step"] = "awaiting_vehicle_location"
                return set_response(
                    state,
                    response="Where is the vehicle currently located?",
                    pending_question="vehicle_location",
                    pending_field="vehicle.current_location",
                    input_type="text",
                )

        # Skip to driver confirmation
        state["state_step"] = "awaiting_driver_confirm"
        return _ask_driver_confirmation(state)

    # Step 7: Handle vehicle location (if not drivable)
    if step == "awaiting_vehicle_location":
        vehicles = state.get("vehicles", [])
        if vehicles:
            vehicles[0]["current_location"] = user_input
            vehicles[0]["tow_needed"] = True
            state["vehicles"] = vehicles

        state["state_step"] = "awaiting_driver_confirm"
        return _ask_driver_confirmation(state)

    # Step 8: Driver confirmation
    if step == "awaiting_driver_confirm":
        user_input_lower = user_input.lower()

        if "yes" in user_input_lower or "i was" in user_input_lower or "me" in user_input_lower:
            # User was driving
            policy_match = state.get("policy_match", {})
            driver = PartyData(
                party_id=str(uuid.uuid4()),
                role="insured_driver",
                first_name=policy_match.get("holder_name", "").split()[0] if policy_match.get("holder_name") else None,
                last_name=policy_match.get("holder_name", "").split()[-1] if policy_match.get("holder_name") and len(policy_match.get("holder_name", "").split()) > 1 else None,
                has_permission=True,
            )

            # Link to vehicle
            vehicles = state.get("vehicles", [])
            if vehicles:
                driver["vehicle_id"] = vehicles[0].get("vehicle_id")

            state["parties"] = [driver]

            state["state_step"] = "complete"
            state = transition_state(state, "THIRD_PARTIES", "initial")
            return state

        elif "no" in user_input_lower or "someone else" in user_input_lower:
            state["state_step"] = "awaiting_driver_name"
            return set_response(
                state,
                response="Who was driving the vehicle? Please provide their name.",
                pending_question="driver_name",
                pending_field="driver.name",
                input_type="text",
            )

        return set_response(
            state,
            response="Were you the one driving the vehicle at the time of the incident?",
            pending_question="driver_confirm",
            pending_field="driver.is_insured",
            input_type="yesno",
            options=[
                {"value": "yes", "label": "Yes, I was driving"},
                {"value": "no", "label": "No, someone else was driving"},
            ],
        )

    # Step 9: Other driver name
    if step == "awaiting_driver_name":
        name_parts = user_input.split()
        first_name = name_parts[0] if name_parts else user_input
        last_name = name_parts[-1] if len(name_parts) > 1 else None

        driver = PartyData(
            party_id=str(uuid.uuid4()),
            role="insured_driver",
            first_name=first_name,
            last_name=last_name,
            has_permission=None,  # Will ask
        )

        vehicles = state.get("vehicles", [])
        if vehicles:
            driver["vehicle_id"] = vehicles[0].get("vehicle_id")

        state["parties"] = [driver]
        state["state_step"] = "awaiting_driver_permission"

        return set_response(
            state,
            response=f"Did {first_name} have your permission to drive the vehicle?",
            pending_question="driver_permission",
            pending_field="driver.has_permission",
            input_type="yesno",
            options=[
                {"value": "yes", "label": "Yes, they had permission"},
                {"value": "no", "label": "No, they didn't have permission"},
            ],
        )

    # Step 10: Driver permission
    if step == "awaiting_driver_permission":
        parties = state.get("parties", [])
        if parties:
            has_permission = "yes" in user_input.lower()
            parties[0]["has_permission"] = has_permission
            state["parties"] = parties

        state["state_step"] = "complete"
        state = transition_state(state, "THIRD_PARTIES", "initial")
        return state

    # Default transition
    state = transition_state(state, "THIRD_PARTIES", "initial")
    return state


def _ask_driver_confirmation(state: FNOLConversationState) -> FNOLConversationState:
    """Ask if the insured was driving."""
    return set_response(
        state,
        response="Were you the one driving the vehicle at the time of the incident?",
        pending_question="driver_confirm",
        pending_field="driver.is_insured",
        input_type="yesno",
        options=[
            {"value": "yes", "label": "Yes, I was driving"},
            {"value": "no", "label": "No, someone else was driving"},
        ],
    )


def extract_year(text: str) -> Optional[int]:
    """Extract year from text."""
    import re
    match = re.search(r'\b(19|20)\d{2}\b', text)
    if match:
        year = int(match.group())
        if 1980 <= year <= 2030:
            return year
    return None
