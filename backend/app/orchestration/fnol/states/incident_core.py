"""
INCIDENT_CORE State Handler

Collects basic incident information:
1. Loss type (collision, theft, weather, etc.)
2. Date and time of incident
3. Location
4. Brief description/narrative

This data is used to detect which scenario playbooks to activate.
"""
from typing import Optional
from datetime import datetime, date
import re

from app.orchestration.fnol.state import FNOLConversationState, IncidentData
from app.orchestration.fnol.states.base import (
    add_audit_event,
    transition_state,
    set_response,
)


# Loss type options for user selection
LOSS_TYPE_OPTIONS = [
    {"value": "collision", "label": "Collision/Accident", "description": "Hit another vehicle, object, or animal"},
    {"value": "theft", "label": "Theft", "description": "Vehicle stolen or items taken from vehicle"},
    {"value": "weather", "label": "Weather Damage", "description": "Hail, flood, wind, fallen tree"},
    {"value": "vandalism", "label": "Vandalism", "description": "Intentional damage to vehicle"},
    {"value": "glass", "label": "Glass Only", "description": "Windshield or window damage only"},
    {"value": "fire", "label": "Fire", "description": "Vehicle fire or smoke damage"},
    {"value": "other", "label": "Other", "description": "Something else"},
]


def incident_core_node(state: FNOLConversationState) -> FNOLConversationState:
    """
    Process the INCIDENT_CORE state.

    Collects:
    - Loss type
    - Date/time
    - Location
    - Description

    Args:
        state: Current conversation state

    Returns:
        Updated conversation state
    """
    step = state.get("state_step", "initial")
    user_input = state.get("current_input", "").strip()
    incident = state.get("incident", IncidentData())

    # Step 1: Initial - Ask what happened
    if step == "initial":
        state["state_step"] = "awaiting_loss_type"
        return set_response(
            state,
            response="What type of incident are you reporting?",
            pending_question="loss_type",
            pending_field="incident.loss_type",
            input_type="select",
            options=LOSS_TYPE_OPTIONS,
        )

    # Step 2: Handle loss type selection
    if step == "awaiting_loss_type":
        loss_type = extract_loss_type(user_input)

        if not loss_type:
            return set_response(
                state,
                response="Please select the type of incident from the options below.",
                pending_question="loss_type",
                pending_field="incident.loss_type",
                input_type="select",
                options=LOSS_TYPE_OPTIONS,
                validation_errors=["Please select an incident type"],
            )

        incident["loss_type"] = loss_type
        state["incident"] = incident

        state = add_audit_event(
            state,
            action="loss_type_set",
            actor="user",
            field_changed="incident.loss_type",
            data_after=loss_type,
        )

        state["state_step"] = "awaiting_date"
        return set_response(
            state,
            response="When did this incident occur? Please provide the date.",
            pending_question="incident_date",
            pending_field="incident.date",
            input_type="date",
        )

    # Step 3: Handle date input
    if step == "awaiting_date":
        parsed_date, is_approximate = parse_date(user_input)

        if not parsed_date:
            return set_response(
                state,
                response="I couldn't understand that date. Please enter the date (for example: January 15, 2024 or 01/15/2024).",
                pending_question="incident_date",
                pending_field="incident.date",
                input_type="date",
                validation_errors=["Please enter a valid date"],
            )

        # Validate date is not in future
        if parsed_date > date.today():
            return set_response(
                state,
                response="The date cannot be in the future. When did the incident occur?",
                pending_question="incident_date",
                pending_field="incident.date",
                input_type="date",
                validation_errors=["Date cannot be in the future"],
            )

        incident["date"] = parsed_date.isoformat()
        incident["time_approximate"] = is_approximate
        state["incident"] = incident

        state = add_audit_event(
            state,
            action="incident_date_set",
            actor="user",
            field_changed="incident.date",
            data_after=parsed_date.isoformat(),
        )

        state["state_step"] = "awaiting_time"
        return set_response(
            state,
            response="What time did it happen? (If you're not sure of the exact time, an approximate time is fine.)",
            pending_question="incident_time",
            pending_field="incident.time",
            input_type="text",
            allow_skip=True,
        )

    # Step 4: Handle time input
    if step == "awaiting_time":
        # Allow skipping
        if user_input.lower() in ["skip", "not sure", "don't know", "unknown", "i don't know"]:
            incident["time"] = None
            incident["time_approximate"] = True
        else:
            parsed_time, is_approximate = parse_time(user_input)
            if parsed_time:
                incident["time"] = parsed_time
                incident["time_approximate"] = is_approximate
            else:
                incident["time"] = None
                incident["time_approximate"] = True

        state["incident"] = incident

        state["state_step"] = "awaiting_location"
        return set_response(
            state,
            response="Where did the incident occur? Please provide the address or describe the location.",
            pending_question="incident_location",
            pending_field="incident.location_raw",
            input_type="text",
        )

    # Step 5: Handle location input
    if step == "awaiting_location":
        if len(user_input) < 5:
            return set_response(
                state,
                response="Please provide more details about where the incident occurred (street address, intersection, or landmark).",
                pending_question="incident_location",
                pending_field="incident.location_raw",
                input_type="text",
                validation_errors=["Please provide a more specific location"],
            )

        incident["location_raw"] = user_input
        # In production, would geocode here to get normalized address and lat/lng
        incident["location_normalized"] = user_input  # Placeholder
        state["incident"] = incident

        state = add_audit_event(
            state,
            action="incident_location_set",
            actor="user",
            field_changed="incident.location_raw",
            data_after=user_input,
        )

        state["state_step"] = "awaiting_description"
        return set_response(
            state,
            response="Please describe what happened in your own words. Include as many details as you can remember.",
            pending_question="incident_description",
            pending_field="incident.description",
            input_type="text",
        )

    # Step 6: Handle description input
    if step == "awaiting_description":
        if len(user_input) < 20:
            return set_response(
                state,
                response="Please provide a bit more detail about what happened. This helps us process your claim accurately.",
                pending_question="incident_description",
                pending_field="incident.description",
                input_type="text",
                validation_errors=["Please provide more details"],
            )

        incident["description"] = user_input
        state["incident"] = incident

        state = add_audit_event(
            state,
            action="incident_description_set",
            actor="user",
            field_changed="incident.description",
            data_after=user_input[:100] + "..." if len(user_input) > 100 else user_input,
        )

        # Check if we need to ask follow-up questions based on loss type
        loss_type = incident.get("loss_type")

        if loss_type == "collision":
            state["state_step"] = "awaiting_collision_details"
            return set_response(
                state,
                response="How many vehicles were involved in this collision?",
                pending_question="vehicle_count",
                pending_field="collision.vehicle_count",
                input_type="select",
                options=[
                    {"value": "1", "label": "Just my vehicle (single vehicle)"},
                    {"value": "2", "label": "Two vehicles"},
                    {"value": "3+", "label": "Three or more vehicles"},
                ],
            )

        if loss_type == "weather":
            state["state_step"] = "awaiting_weather_type"
            return set_response(
                state,
                response="What type of weather damage occurred?",
                pending_question="weather_type",
                pending_field="incident.loss_subtype",
                input_type="select",
                options=[
                    {"value": "hail", "label": "Hail damage"},
                    {"value": "flood", "label": "Flood/Water damage"},
                    {"value": "wind", "label": "Wind damage"},
                    {"value": "tree", "label": "Fallen tree/branch"},
                ],
            )

        if loss_type == "theft":
            state["state_step"] = "awaiting_theft_type"
            return set_response(
                state,
                response="Was your vehicle stolen, or were items stolen from your vehicle?",
                pending_question="theft_type",
                pending_field="incident.loss_subtype",
                input_type="select",
                options=[
                    {"value": "vehicle_stolen", "label": "Vehicle was stolen"},
                    {"value": "attempted_theft", "label": "Attempted theft (vehicle not taken)"},
                    {"value": "items_stolen", "label": "Items stolen from vehicle"},
                ],
            )

        # For other types, proceed to LOSS_MODULE
        state["state_step"] = "complete"
        state = transition_state(state, "LOSS_MODULE", "initial")
        return state

    # Step 7: Handle collision details
    if step == "awaiting_collision_details":
        vehicle_count = extract_number(user_input)

        if vehicle_count == 1 or "just" in user_input.lower() or "single" in user_input.lower() or "my" in user_input.lower():
            incident["loss_subtype"] = "single_vehicle"
            state["state_data"]["involved_vehicles"] = 1
        elif vehicle_count == 2 or "two" in user_input.lower():
            incident["loss_subtype"] = "two_vehicle"
            state["state_data"]["involved_vehicles"] = 2
        elif vehicle_count and vehicle_count >= 3 or "three" in user_input.lower() or "more" in user_input.lower():
            incident["loss_subtype"] = "multi_vehicle"
            state["state_data"]["involved_vehicles"] = vehicle_count or 3
        else:
            return set_response(
                state,
                response="Please select how many vehicles were involved.",
                pending_question="vehicle_count",
                pending_field="collision.vehicle_count",
                input_type="select",
                options=[
                    {"value": "1", "label": "Just my vehicle"},
                    {"value": "2", "label": "Two vehicles"},
                    {"value": "3+", "label": "Three or more"},
                ],
            )

        state["incident"] = incident

        # For collisions, ask about the other party
        if state["state_data"].get("involved_vehicles", 1) > 1:
            state["state_step"] = "awaiting_other_party_known"
            return set_response(
                state,
                response="Did you get the other driver's information?",
                pending_question="other_party_known",
                pending_field="collision.other_party_known",
                input_type="yesno",
                options=[
                    {"value": "yes", "label": "Yes, I have their info"},
                    {"value": "no", "label": "No, they left the scene"},
                    {"value": "partial", "label": "I have some information"},
                ],
            )

        state["state_step"] = "complete"
        state = transition_state(state, "LOSS_MODULE", "initial")
        return state

    # Step 8: Handle other party known
    if step == "awaiting_other_party_known":
        incident = state.get("incident", {})

        if "no" in user_input.lower() or "left" in user_input.lower():
            incident["loss_subtype"] = "hit_and_run"
            state["state_data"]["other_party_known"] = False
        elif "partial" in user_input.lower() or "some" in user_input.lower():
            state["state_data"]["other_party_known"] = "partial"
        else:
            state["state_data"]["other_party_known"] = True

        state["incident"] = incident
        state["state_step"] = "complete"
        state = transition_state(state, "LOSS_MODULE", "initial")
        return state

    # Step 9: Handle weather type
    if step == "awaiting_weather_type":
        weather_type = extract_weather_type(user_input)

        if weather_type:
            incident["loss_subtype"] = weather_type
            state["incident"] = incident

        state["state_step"] = "complete"
        state = transition_state(state, "LOSS_MODULE", "initial")
        return state

    # Step 10: Handle theft type
    if step == "awaiting_theft_type":
        theft_type = extract_theft_type(user_input)

        if theft_type:
            incident["loss_subtype"] = theft_type
            state["incident"] = incident

        state["state_step"] = "complete"
        state = transition_state(state, "LOSS_MODULE", "initial")
        return state

    # Default: transition to next state
    state = transition_state(state, "LOSS_MODULE", "initial")
    return state


# Helper functions

def extract_loss_type(text: str) -> Optional[str]:
    """Extract loss type from user input."""
    text_lower = text.lower()

    mappings = {
        "collision": ["collision", "accident", "crash", "hit", "rear-end", "fender", "wreck"],
        "theft": ["theft", "stolen", "stole", "break-in", "broke into"],
        "weather": ["weather", "hail", "flood", "storm", "wind", "tree", "lightning"],
        "vandalism": ["vandalism", "vandal", "keyed", "scratched", "graffiti", "broken into"],
        "glass": ["glass", "windshield", "window", "crack", "chip"],
        "fire": ["fire", "burn", "smoke", "flame"],
    }

    for loss_type, keywords in mappings.items():
        if any(kw in text_lower for kw in keywords):
            return loss_type

    # Check for exact match from options
    for option in LOSS_TYPE_OPTIONS:
        if option["value"] in text_lower or text_lower in option["value"]:
            return option["value"]

    return None


def parse_date(text: str) -> tuple[Optional[date], bool]:
    """
    Parse date from user input.
    Returns (date, is_approximate).
    """
    text_lower = text.lower().strip()
    is_approximate = "around" in text_lower or "about" in text_lower or "approximately" in text_lower

    # Handle relative dates
    today = date.today()

    if "today" in text_lower:
        return today, False
    if "yesterday" in text_lower:
        from datetime import timedelta
        return today - timedelta(days=1), False
    if "last night" in text_lower:
        from datetime import timedelta
        return today - timedelta(days=1), True

    # Try various date formats
    import re
    from datetime import datetime as dt

    # Clean the text
    text_clean = re.sub(r'(around|about|approximately|on)\s*', '', text_lower).strip()

    formats = [
        "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y",
        "%Y-%m-%d", "%Y/%m/%d",
        "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y",
        "%d %B %Y", "%d %b %Y",
        "%m/%d", "%m-%d",  # Current year assumed
    ]

    for fmt in formats:
        try:
            parsed = dt.strptime(text_clean, fmt)
            # Handle formats without year
            if parsed.year == 1900:
                parsed = parsed.replace(year=today.year)
            return parsed.date(), is_approximate
        except ValueError:
            continue

    return None, False


def parse_time(text: str) -> tuple[Optional[str], bool]:
    """
    Parse time from user input.
    Returns (time_string, is_approximate).
    """
    text_lower = text.lower().strip()
    is_approximate = any(word in text_lower for word in ["around", "about", "approximately", "roughly", "ish"])

    # Handle common time descriptions
    time_mappings = {
        "morning": "09:00",
        "afternoon": "14:00",
        "evening": "18:00",
        "night": "21:00",
        "midnight": "00:00",
        "noon": "12:00",
        "midday": "12:00",
    }

    for desc, time_val in time_mappings.items():
        if desc in text_lower:
            return time_val, True

    # Try to parse specific times
    import re

    # Pattern: HH:MM AM/PM or HH AM/PM
    time_pattern = r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?'
    match = re.search(time_pattern, text_lower)

    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        period = match.group(3)

        if period and ('p' in period) and hour < 12:
            hour += 12
        elif period and ('a' in period) and hour == 12:
            hour = 0

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}", is_approximate

    return None, False


def extract_number(text: str) -> Optional[int]:
    """Extract a number from text."""
    import re

    # Word to number mapping
    word_nums = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }

    text_lower = text.lower()
    for word, num in word_nums.items():
        if word in text_lower:
            return num

    # Try to find a digit
    match = re.search(r'\d+', text)
    if match:
        return int(match.group())

    return None


def extract_weather_type(text: str) -> Optional[str]:
    """Extract weather type from input."""
    text_lower = text.lower()

    if "hail" in text_lower:
        return "hail"
    if "flood" in text_lower or "water" in text_lower:
        return "flood"
    if "wind" in text_lower:
        return "wind"
    if "tree" in text_lower or "branch" in text_lower:
        return "tree"

    return None


def extract_theft_type(text: str) -> Optional[str]:
    """Extract theft type from input."""
    text_lower = text.lower()

    if "vehicle" in text_lower and "stolen" in text_lower:
        return "vehicle_stolen"
    if "attempt" in text_lower:
        return "attempted_theft"
    if "item" in text_lower or "from" in text_lower:
        return "items_stolen"
    if "stolen" in text_lower:
        return "vehicle_stolen"

    return None
