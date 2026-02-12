"""
THIRD_PARTIES State Handler

Collects information about other parties involved:
- Other drivers and their vehicles
- Passengers
- Witnesses
- For multi-vehicle: impact graph
"""
from typing import Optional
import uuid

from app.orchestration.fnol.state import FNOLConversationState, VehicleData, PartyData, ImpactData
from app.orchestration.fnol.states.base import (
    add_audit_event,
    transition_state,
    set_response,
)


def third_parties_node(state: FNOLConversationState) -> FNOLConversationState:
    """Process the THIRD_PARTIES state."""
    step = state.get("state_step", "initial")
    user_input = state.get("current_input", "").strip()
    incident = state.get("incident", {})
    loss_subtype = incident.get("loss_subtype", "")

    # Check if this scenario needs third party info
    if step == "initial":
        # Single vehicle accidents don't need third party
        if loss_subtype in ["single_vehicle", "weather_hail", "weather_flood", "theft_vehicle", "vandalism", "glass_only"]:
            state["state_step"] = "skipped"
            state = transition_state(state, "INJURIES", "initial")
            return state

        # Hit and run - other party unknown
        if loss_subtype == "hit_and_run":
            state["state_step"] = "awaiting_hit_run_details"
            return set_response(
                state,
                response="Since the other driver left the scene, do you have any information about their vehicle? (license plate, make/model, color, direction they went)",
                pending_question="hit_run_details",
                pending_field="third_party.description",
                input_type="text",
                allow_skip=True,
            )

        # Two or multi-vehicle collision
        state["state_step"] = "awaiting_other_driver_info"
        return set_response(
            state,
            response="Do you have the other driver's contact information?",
            pending_question="other_driver_info",
            pending_field="third_party.has_info",
            input_type="yesno",
            options=[
                {"value": "yes", "label": "Yes, I have their info"},
                {"value": "no", "label": "No, I don't have it"},
                {"value": "partial", "label": "I have some information"},
            ],
        )

    # Handle hit and run details
    if step == "awaiting_hit_run_details":
        # Create unknown party record
        other_party = PartyData(
            party_id=str(uuid.uuid4()),
            role="third_party_driver",
            is_unknown=True,
            unknown_description=user_input if user_input.lower() not in ["skip", "none", "no"] else None,
        )

        # Create unknown vehicle
        other_vehicle = VehicleData(
            vehicle_id=str(uuid.uuid4()),
            role="unknown",
        )

        # Parse any details from description
        if user_input and user_input.lower() not in ["skip", "none", "no"]:
            parsed = parse_vehicle_description(user_input)
            if parsed:
                other_vehicle.update(parsed)

        vehicles = state.get("vehicles", [])
        vehicles.append(other_vehicle)
        state["vehicles"] = vehicles

        parties = state.get("parties", [])
        other_party["vehicle_id"] = other_vehicle["vehicle_id"]
        parties.append(other_party)
        state["parties"] = parties

        # Ask about witnesses
        state["state_step"] = "awaiting_witnesses"
        return set_response(
            state,
            response="Were there any witnesses to the incident?",
            pending_question="witnesses",
            pending_field="witnesses.any",
            input_type="yesno",
            options=[
                {"value": "yes", "label": "Yes, there were witnesses"},
                {"value": "no", "label": "No witnesses"},
            ],
        )

    # Handle other driver info availability
    if step == "awaiting_other_driver_info":
        has_info = "yes" in user_input.lower() or "have" in user_input.lower()
        partial = "partial" in user_input.lower() or "some" in user_input.lower()

        if has_info or partial:
            state["state_step"] = "awaiting_other_driver_name"
            return set_response(
                state,
                response="What is the other driver's name?",
                pending_question="other_driver_name",
                pending_field="third_party.name",
                input_type="text",
                allow_skip=True,
            )
        else:
            # No info - ask about witnesses
            state["state_step"] = "awaiting_witnesses"
            return set_response(
                state,
                response="Were there any witnesses to the incident?",
                pending_question="witnesses",
                pending_field="witnesses.any",
                input_type="yesno",
            )

    # Collect other driver name
    if step == "awaiting_other_driver_name":
        name_parts = user_input.split() if user_input.lower() not in ["skip", "unknown"] else []
        first_name = name_parts[0] if name_parts else None
        last_name = name_parts[-1] if len(name_parts) > 1 else None

        other_party = PartyData(
            party_id=str(uuid.uuid4()),
            role="third_party_driver",
            first_name=first_name,
            last_name=last_name,
            is_unknown=not bool(first_name),
        )

        parties = state.get("parties", [])
        parties.append(other_party)
        state["parties"] = parties
        state["state_data"]["current_third_party_id"] = other_party["party_id"]

        state["state_step"] = "awaiting_other_driver_phone"
        return set_response(
            state,
            response="What is their phone number?",
            pending_question="other_driver_phone",
            pending_field="third_party.phone",
            input_type="text",
            allow_skip=True,
        )

    # Collect other driver phone
    if step == "awaiting_other_driver_phone":
        parties = state.get("parties", [])
        current_id = state.get("state_data", {}).get("current_third_party_id")

        for party in parties:
            if party.get("party_id") == current_id:
                if user_input.lower() not in ["skip", "unknown", "none"]:
                    party["phone"] = extract_phone(user_input)
                break

        state["parties"] = parties
        state["state_step"] = "awaiting_other_vehicle_info"

        return set_response(
            state,
            response="What information do you have about their vehicle? (year, make, model, color, or license plate)",
            pending_question="other_vehicle_info",
            pending_field="third_party_vehicle",
            input_type="text",
            allow_skip=True,
        )

    # Collect other vehicle info
    if step == "awaiting_other_vehicle_info":
        other_vehicle = VehicleData(
            vehicle_id=str(uuid.uuid4()),
            role="third_party",
        )

        if user_input.lower() not in ["skip", "unknown", "none"]:
            parsed = parse_vehicle_description(user_input)
            if parsed:
                other_vehicle.update(parsed)

        vehicles = state.get("vehicles", [])
        vehicles.append(other_vehicle)
        state["vehicles"] = vehicles

        # Link party to vehicle
        parties = state.get("parties", [])
        current_id = state.get("state_data", {}).get("current_third_party_id")
        for party in parties:
            if party.get("party_id") == current_id:
                party["vehicle_id"] = other_vehicle["vehicle_id"]
                break
        state["parties"] = parties

        state["state_step"] = "awaiting_other_insurance"
        return set_response(
            state,
            response="Do you have their insurance information?",
            pending_question="other_insurance",
            pending_field="third_party.insurance",
            input_type="yesno",
            options=[
                {"value": "yes", "label": "Yes, I have it"},
                {"value": "no", "label": "No"},
            ],
        )

    # Collect other insurance
    if step == "awaiting_other_insurance":
        has_insurance = "yes" in user_input.lower()

        if has_insurance:
            state["state_step"] = "awaiting_insurance_details"
            return set_response(
                state,
                response="What is their insurance company and policy number (if available)?",
                pending_question="insurance_details",
                pending_field="third_party.insurance_details",
                input_type="text",
            )

        state["state_step"] = "awaiting_witnesses"
        return set_response(
            state,
            response="Were there any witnesses to the incident?",
            pending_question="witnesses",
            pending_field="witnesses.any",
            input_type="yesno",
        )

    # Collect insurance details
    if step == "awaiting_insurance_details":
        parties = state.get("parties", [])
        current_id = state.get("state_data", {}).get("current_third_party_id")

        for party in parties:
            if party.get("party_id") == current_id:
                # Parse insurance info
                carrier, policy_num = parse_insurance_info(user_input)
                party["insurance_carrier"] = carrier
                party["insurance_policy_number"] = policy_num
                break

        state["parties"] = parties
        state["state_step"] = "awaiting_witnesses"

        return set_response(
            state,
            response="Were there any witnesses to the incident?",
            pending_question="witnesses",
            pending_field="witnesses.any",
            input_type="yesno",
        )

    # Handle witnesses
    if step == "awaiting_witnesses":
        has_witnesses = "yes" in user_input.lower()

        if has_witnesses:
            state["state_step"] = "awaiting_witness_count"
            return set_response(
                state,
                response="How many witnesses were there?",
                pending_question="witness_count",
                pending_field="witnesses.count",
                input_type="text",
            )

        state["state_step"] = "complete"
        state = transition_state(state, "INJURIES", "initial")
        return state

    # Handle witness count
    if step == "awaiting_witness_count":
        # Just note that witnesses exist, don't collect all details now
        state["state_data"]["has_witnesses"] = True

        state = add_audit_event(
            state,
            action="witnesses_noted",
            actor="user",
            data_after={"has_witnesses": True},
        )

        state["state_step"] = "complete"
        state = transition_state(state, "INJURIES", "initial")
        return state

    # Default transition
    state = transition_state(state, "INJURIES", "initial")
    return state


def parse_vehicle_description(text: str) -> dict:
    """Parse vehicle details from free text description."""
    import re

    result = {}
    text_lower = text.lower()

    # Extract year
    year_match = re.search(r'\b(19|20)\d{2}\b', text)
    if year_match:
        result["year"] = int(year_match.group())

    # Extract color
    colors = ["black", "white", "silver", "gray", "grey", "red", "blue", "green", "yellow", "orange", "brown", "gold", "beige", "tan"]
    for color in colors:
        if color in text_lower:
            result["color"] = color.title()
            break

    # Extract plate
    plate_match = re.search(r'\b[A-Z0-9]{5,8}\b', text.upper())
    if plate_match:
        result["license_plate"] = plate_match.group()

    # Common makes
    makes = ["honda", "toyota", "ford", "chevrolet", "chevy", "nissan", "hyundai", "kia", "bmw", "mercedes", "audi", "volkswagen", "vw", "subaru", "mazda", "lexus", "jeep", "dodge", "ram", "gmc", "buick", "cadillac", "lincoln", "acura", "infiniti", "tesla"]
    for make in makes:
        if make in text_lower:
            result["make"] = make.title()
            if make == "chevy":
                result["make"] = "Chevrolet"
            elif make == "vw":
                result["make"] = "Volkswagen"
            break

    return result


def extract_phone(text: str) -> Optional[str]:
    """Extract phone number from text."""
    import re
    digits = re.sub(r'\D', '', text)
    if len(digits) == 11 and digits[0] == '1':
        digits = digits[1:]
    if len(digits) == 10:
        return digits
    return None


def parse_insurance_info(text: str) -> tuple:
    """Parse insurance carrier and policy number from text."""
    import re

    carriers = ["state farm", "geico", "progressive", "allstate", "usaa", "liberty mutual", "farmers", "nationwide", "travelers", "american family", "aaa"]

    carrier = None
    for c in carriers:
        if c in text.lower():
            carrier = c.title()
            break

    # Look for policy number pattern
    policy_match = re.search(r'\b[A-Z0-9]{6,15}\b', text.upper())
    policy_num = policy_match.group() if policy_match else None

    return carrier, policy_num
