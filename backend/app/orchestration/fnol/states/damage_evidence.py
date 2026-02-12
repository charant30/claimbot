"""
DAMAGE_EVIDENCE State Handler

Collects damage information and requests evidence:
- Damage areas on vehicles
- Damage descriptions
- Photo/document requests
"""
from typing import Optional
import uuid

from app.orchestration.fnol.state import FNOLConversationState, DamageData, EvidenceData
from app.orchestration.fnol.states.base import (
    add_audit_event,
    transition_state,
    set_response,
    format_vehicle_display,
)


DAMAGE_AREA_OPTIONS = [
    {"value": "front", "label": "Front"},
    {"value": "rear", "label": "Rear"},
    {"value": "left_side", "label": "Left/Driver side"},
    {"value": "right_side", "label": "Right/Passenger side"},
    {"value": "roof", "label": "Roof"},
    {"value": "windshield", "label": "Windshield"},
    {"value": "side_window", "label": "Side window(s)"},
    {"value": "hood", "label": "Hood"},
    {"value": "trunk", "label": "Trunk"},
    {"value": "undercarriage", "label": "Undercarriage"},
    {"value": "total", "label": "Total loss/All over"},
]


def damage_evidence_node(state: FNOLConversationState) -> FNOLConversationState:
    """Process the DAMAGE_EVIDENCE state."""
    step = state.get("state_step", "initial")
    user_input = state.get("current_input", "").strip()
    vehicles = state.get("vehicles", [])

    # Step 1: Initial - Ask about damage areas
    if step == "initial":
        # Find insured vehicle
        insured_vehicle = None
        for v in vehicles:
            if v.get("role") == "insured":
                insured_vehicle = v
                break

        if insured_vehicle:
            display = format_vehicle_display(insured_vehicle)
            state["state_data"]["current_vehicle_id"] = insured_vehicle.get("vehicle_id")
        else:
            display = "your vehicle"

        state["state_step"] = "awaiting_damage_areas"
        return set_response(
            state,
            response=f"Which areas of {display} were damaged? (You can select multiple)",
            pending_question="damage_areas",
            pending_field="damage.areas",
            input_type="multiselect",
            options=DAMAGE_AREA_OPTIONS,
        )

    # Step 2: Handle damage areas
    if step == "awaiting_damage_areas":
        areas = parse_damage_areas(user_input)
        vehicle_id = state.get("state_data", {}).get("current_vehicle_id")

        if not areas:
            return set_response(
                state,
                response="Please select or describe which areas of the vehicle were damaged.",
                pending_question="damage_areas",
                pending_field="damage.areas",
                input_type="multiselect",
                options=DAMAGE_AREA_OPTIONS,
            )

        # Create damage records for each area
        damages = state.get("damages", [])
        for area in areas:
            damage = DamageData(
                damage_id=str(uuid.uuid4()),
                vehicle_id=vehicle_id,
                damage_type="vehicle",
                damage_area=area,
            )
            damages.append(damage)

        state["damages"] = damages
        state["state_data"]["damage_areas"] = areas

        state = add_audit_event(
            state,
            action="damage_areas_recorded",
            actor="user",
            field_changed="damages",
            data_after={"areas": areas},
        )

        state["state_step"] = "awaiting_damage_description"
        return set_response(
            state,
            response="Please describe the damage in more detail.",
            pending_question="damage_description",
            pending_field="damage.description",
            input_type="text",
        )

    # Step 3: Handle damage description
    if step == "awaiting_damage_description":
        damages = state.get("damages", [])
        vehicle_id = state.get("state_data", {}).get("current_vehicle_id")

        # Update descriptions for vehicle damages
        for damage in damages:
            if damage.get("vehicle_id") == vehicle_id:
                damage["description"] = user_input
                break

        state["damages"] = damages
        state["state_step"] = "awaiting_estimate"

        return set_response(
            state,
            response="Do you have an estimate of the damage amount?",
            pending_question="damage_estimate",
            pending_field="damage.estimate",
            input_type="select",
            options=[
                {"value": "unknown", "label": "I don't know yet"},
                {"value": "minor", "label": "Minor (under $1,000)"},
                {"value": "moderate", "label": "Moderate ($1,000 - $5,000)"},
                {"value": "major", "label": "Major ($5,000 - $15,000)"},
                {"value": "total", "label": "Possible total loss (over $15,000)"},
            ],
            allow_skip=True,
        )

    # Step 4: Handle damage estimate
    if step == "awaiting_estimate":
        # Map response to estimated amount
        estimate_map = {
            "minor": 500,
            "moderate": 3000,
            "major": 10000,
            "total": 20000,
        }

        damages = state.get("damages", [])
        vehicle_id = state.get("state_data", {}).get("current_vehicle_id")

        for key, amount in estimate_map.items():
            if key in user_input.lower():
                for damage in damages:
                    if damage.get("vehicle_id") == vehicle_id:
                        damage["estimated_amount"] = amount
                        break
                break

        state["damages"] = damages
        state["state_step"] = "awaiting_property_damage"

        return set_response(
            state,
            response="Was any other property damaged (fences, buildings, etc.)?",
            pending_question="property_damage",
            pending_field="damage.property",
            input_type="yesno",
        )

    # Step 5: Handle property damage
    if step == "awaiting_property_damage":
        has_property_damage = "yes" in user_input.lower()

        if has_property_damage:
            state["state_step"] = "awaiting_property_details"
            return set_response(
                state,
                response="Please describe what property was damaged.",
                pending_question="property_details",
                pending_field="damage.property_description",
                input_type="text",
            )

        state["state_step"] = "request_photos"
        return _request_photos(state)

    # Step 6: Handle property details
    if step == "awaiting_property_details":
        damage = DamageData(
            damage_id=str(uuid.uuid4()),
            damage_type="property",
            description=user_input,
            property_type=extract_property_type(user_input),
        )

        damages = state.get("damages", [])
        damages.append(damage)
        state["damages"] = damages

        state["state_step"] = "request_photos"
        return _request_photos(state)

    # Step 7: Request photos
    if step == "request_photos":
        return _request_photos(state)

    # Step 8: Handle photo upload response
    if step == "awaiting_photos":
        user_lower = user_input.lower()

        if "upload" in user_lower or "yes" in user_lower or "sure" in user_lower:
            # Create pending evidence records
            evidence = state.get("evidence", [])
            photo_types = ["scene", "damage", "vehicle"]

            for photo_type in photo_types:
                ev = EvidenceData(
                    evidence_id=str(uuid.uuid4()),
                    evidence_type="photo",
                    subtype=photo_type,
                    upload_status="pending",
                )
                evidence.append(ev)

            state["evidence"] = evidence
            state["state_step"] = "photos_requested"

            return set_response(
                state,
                response=(
                    "You can upload photos now or later. The following photos are helpful:\n"
                    "- Overall scene photos\n"
                    "- Close-ups of all damage\n"
                    "- License plates of vehicles involved\n"
                    "- VIN sticker (driver's door frame)\n\n"
                    "Would you like to upload photos now, or continue and upload later?"
                ),
                pending_question="upload_now",
                pending_field="photos.upload_now",
                input_type="select",
                options=[
                    {"value": "now", "label": "Upload now"},
                    {"value": "later", "label": "Upload later"},
                ],
            )

        # User doesn't want to upload
        state["state_step"] = "complete"
        state = transition_state(state, "TRIAGE", "initial")
        return state

    # Step 9: Handle upload now/later
    if step == "photos_requested":
        if "now" in user_input.lower():
            state["state_step"] = "uploading_photos"
            return set_response(
                state,
                response="Please upload your photos. You can drag and drop or click to select files.",
                pending_question="photo_upload",
                pending_field="photos",
                input_type="photo",
            )

        state["state_step"] = "complete"
        state = transition_state(state, "TRIAGE", "initial")
        return state

    # Step 10: Handle photo upload
    if step == "uploading_photos":
        # In real implementation, this would handle file uploads
        # For now, just note that photos were provided
        state = add_audit_event(
            state,
            action="photos_uploaded",
            actor="user",
        )

        state["state_step"] = "complete"
        state = transition_state(state, "TRIAGE", "initial")
        return state

    # Default transition
    state = transition_state(state, "TRIAGE", "initial")
    return state


def _request_photos(state: FNOLConversationState) -> FNOLConversationState:
    """Request photos from user."""
    state["state_step"] = "awaiting_photos"
    return set_response(
        state,
        response=(
            "Photos help us process your claim faster. Do you have photos of:\n"
            "- The damage to your vehicle\n"
            "- The accident scene\n"
            "- The other vehicle(s) involved"
        ),
        pending_question="has_photos",
        pending_field="photos.available",
        input_type="yesno",
        options=[
            {"value": "yes", "label": "Yes, I have photos"},
            {"value": "later", "label": "I can take/upload them later"},
            {"value": "no", "label": "No photos available"},
        ],
    )


def parse_damage_areas(text: str) -> list:
    """Parse damage areas from user input."""
    areas = []
    text_lower = text.lower()

    area_keywords = {
        "front": ["front", "bumper", "grille", "headlight", "hood"],
        "rear": ["rear", "back", "trunk", "taillight", "bumper"],
        "left_side": ["left", "driver", "driver's side"],
        "right_side": ["right", "passenger", "passenger's side"],
        "roof": ["roof", "top"],
        "windshield": ["windshield", "front window", "front glass"],
        "side_window": ["side window", "door window"],
        "hood": ["hood"],
        "trunk": ["trunk", "hatch"],
        "undercarriage": ["undercarriage", "bottom", "underneath"],
        "total": ["total", "totaled", "all over", "everywhere", "whole car"],
    }

    for area, keywords in area_keywords.items():
        if any(kw in text_lower for kw in keywords):
            areas.append(area)

    # If nothing matched but user provided input, default to "other"
    if not areas and len(text) > 2:
        areas.append("other")

    return areas


def extract_property_type(text: str) -> Optional[str]:
    """Extract property type from description."""
    text_lower = text.lower()

    types = {
        "fence": ["fence", "fencing"],
        "mailbox": ["mailbox", "mail box"],
        "building": ["building", "wall", "house", "garage"],
        "pole": ["pole", "light pole", "street light"],
        "sign": ["sign", "stop sign", "street sign"],
        "guardrail": ["guardrail", "guard rail", "barrier"],
        "tree": ["tree"],
    }

    for prop_type, keywords in types.items():
        if any(kw in text_lower for kw in keywords):
            return prop_type

    return "other"
