"""
IDENTITY_MATCH State Handler

This state verifies the caller's identity and matches them to a policy.
Methods:
1. Policy number lookup
2. Phone + Name + DOB/ZIP lookup
3. Guest mode (continue without match)

If policy is matched, loads vehicle and driver information.
"""
from typing import Dict, Any, Optional
from datetime import datetime
import re

from app.orchestration.fnol.state import FNOLConversationState, PolicyMatchData
from app.orchestration.fnol.states.base import (
    add_audit_event,
    transition_state,
    set_response,
)


def identity_match_node(state: FNOLConversationState) -> FNOLConversationState:
    """
    Process the IDENTITY_MATCH state.

    Flow:
    1. Ask how they'd like to identify (policy number or personal info)
    2. Attempt to match policy
    3. If matched, load policy details
    4. If not matched, offer guest mode

    Args:
        state: Current conversation state

    Returns:
        Updated conversation state
    """
    step = state.get("state_step", "initial")
    user_input = state.get("current_input", "").strip()

    # Step 1: Initial - Ask for identification method
    if step == "initial":
        # Check if we already have a policy_id from session creation
        policy_match = state.get("policy_match", {})
        if policy_match.get("policy_id"):
            # Policy already known, verify
            state["state_step"] = "verify_policy"
            return _handle_policy_verification(state)

        state["state_step"] = "awaiting_id_method"
        return set_response(
            state,
            response=(
                "To help you file a claim, I'll need to verify your identity.\n\n"
                "Do you have your policy number handy?"
            ),
            pending_question="id_method",
            pending_field="policy_number",
            input_type="yesno",
            options=[
                {"value": "yes", "label": "Yes, I have my policy number"},
                {"value": "no", "label": "No, but I can provide my information"},
            ],
        )

    # Step 2: Handle identification method choice
    if step == "awaiting_id_method":
        has_policy = "yes" in user_input.lower() or "policy" in user_input.lower()

        # Check if user directly provided a policy number
        policy_number = extract_policy_number(user_input)
        if policy_number:
            return _handle_policy_number_input(state, policy_number)

        if has_policy:
            state["state_step"] = "awaiting_policy_number"
            return set_response(
                state,
                response="Please enter your policy number.",
                pending_question="policy_number",
                pending_field="policy_number",
                input_type="text",
                options=[],
            )
        else:
            state["state_step"] = "awaiting_phone"
            return set_response(
                state,
                response="No problem. Let's find your policy using your information.\n\nWhat is the phone number on your policy?",
                pending_question="phone_number",
                pending_field="holder_phone",
                input_type="text",
                options=[],
            )

    # Step 3: Handle policy number input
    if step == "awaiting_policy_number":
        policy_number = extract_policy_number(user_input)
        if not policy_number:
            return set_response(
                state,
                response="I couldn't find a valid policy number in that. Please enter your policy number (it usually starts with letters followed by numbers).",
                pending_question="policy_number",
                pending_field="policy_number",
                input_type="text",
                validation_errors=["Invalid policy number format"],
            )

        return _handle_policy_number_input(state, policy_number)

    # Step 4: Handle phone number input
    if step == "awaiting_phone":
        phone = extract_phone_number(user_input)
        if not phone:
            return set_response(
                state,
                response="Please enter a valid phone number (10 digits).",
                pending_question="phone_number",
                pending_field="holder_phone",
                input_type="text",
                validation_errors=["Invalid phone number"],
            )

        state["state_data"]["holder_phone"] = phone
        state["state_step"] = "awaiting_name"

        return set_response(
            state,
            response="Thank you. What is your full name as it appears on the policy?",
            pending_question="holder_name",
            pending_field="holder_name",
            input_type="text",
        )

    # Step 5: Handle name input
    if step == "awaiting_name":
        name = user_input.strip()
        if len(name) < 2:
            return set_response(
                state,
                response="Please enter your full name.",
                pending_question="holder_name",
                pending_field="holder_name",
                input_type="text",
                validation_errors=["Name is required"],
            )

        state["state_data"]["holder_name"] = name
        state["state_step"] = "awaiting_zip"

        return set_response(
            state,
            response="And what is your ZIP code?",
            pending_question="holder_zip",
            pending_field="holder_zip",
            input_type="text",
        )

    # Step 6: Handle ZIP code input
    if step == "awaiting_zip":
        zip_code = extract_zip_code(user_input)
        if not zip_code:
            return set_response(
                state,
                response="Please enter a valid 5-digit ZIP code.",
                pending_question="holder_zip",
                pending_field="holder_zip",
                input_type="text",
                validation_errors=["Invalid ZIP code"],
            )

        state["state_data"]["holder_zip"] = zip_code

        # Attempt lookup by personal info
        return _handle_personal_info_lookup(state)

    # Step 7: Verify policy (OTP or confirmation)
    if step == "verify_policy":
        return _handle_policy_verification(state)

    # Step 8: Handle verification confirmation
    if step == "awaiting_verification":
        is_correct = "yes" in user_input.lower() or "correct" in user_input.lower() or "that's me" in user_input.lower()

        if is_correct:
            # Policy verified
            policy_match = state.get("policy_match", {})
            policy_match["status"] = "matched"
            state["policy_match"] = policy_match

            state = add_audit_event(
                state,
                action="policy_verified",
                actor="user",
                field_changed="policy_match.status",
                data_after="matched",
            )

            state = transition_state(state, "INCIDENT_CORE", "initial")
            return state

        # Not correct - offer alternatives
        state["state_step"] = "wrong_policy"
        return set_response(
            state,
            response=(
                "I apologize for the confusion. Would you like to:\n"
                "1. Try a different policy number\n"
                "2. Search using your personal information\n"
                "3. Continue without matching a policy"
            ),
            pending_question="wrong_policy_action",
            pending_field="id_method",
            input_type="select",
            options=[
                {"value": "policy", "label": "Try different policy number"},
                {"value": "info", "label": "Search by personal info"},
                {"value": "guest", "label": "Continue as guest"},
            ],
        )

    # Step 9: Handle wrong policy options
    if step == "wrong_policy":
        choice = user_input.lower()

        if "policy" in choice or "1" in choice or "different" in choice:
            state["state_step"] = "awaiting_policy_number"
            return set_response(
                state,
                response="Please enter your policy number.",
                pending_question="policy_number",
                pending_field="policy_number",
                input_type="text",
            )

        if "info" in choice or "2" in choice or "personal" in choice:
            state["state_step"] = "awaiting_phone"
            return set_response(
                state,
                response="What is the phone number on your policy?",
                pending_question="phone_number",
                pending_field="holder_phone",
                input_type="text",
            )

        # Guest mode
        return _setup_guest_mode(state)

    # Step 10: Handle no policy found
    if step == "no_policy_found":
        wants_guest = "guest" in user_input.lower() or "continue" in user_input.lower() or "yes" in user_input.lower()

        if wants_guest:
            return _setup_guest_mode(state)

        # Try again
        state["state_step"] = "awaiting_id_method"
        return set_response(
            state,
            response="Would you like to try searching again with your policy number or personal information?",
            pending_question="id_method",
            pending_field="policy_number",
            input_type="yesno",
            options=[
                {"value": "yes", "label": "Yes, I'll try my policy number"},
                {"value": "no", "label": "Use my personal information"},
            ],
        )

    # Default: transition to next state
    state = transition_state(state, "INCIDENT_CORE", "initial")
    return state


def _handle_policy_number_input(state: FNOLConversationState, policy_number: str) -> FNOLConversationState:
    """Handle policy number lookup."""
    # In a real implementation, this would call the policy service
    # For now, simulate a lookup

    state["state_data"]["policy_number"] = policy_number

    # Simulate policy lookup (replace with actual service call)
    policy_data = _simulate_policy_lookup(policy_number)

    if policy_data:
        # Policy found
        state["policy_match"] = PolicyMatchData(
            status="pending",  # Pending verification
            policy_id=policy_data.get("policy_id"),
            policy_number=policy_number,
            method="policy_number",
            confidence=1.0,
            holder_name=policy_data.get("holder_name"),
            vehicles=policy_data.get("vehicles", []),
            drivers=policy_data.get("drivers", []),
        )

        state["state_step"] = "awaiting_verification"

        # Ask for confirmation
        holder_name = policy_data.get("holder_name", "Unknown")
        return set_response(
            state,
            response=f"I found a policy for **{holder_name}**. Is this correct?",
            pending_question="verify_identity",
            pending_field="identity_confirmed",
            input_type="yesno",
            options=[
                {"value": "yes", "label": "Yes, that's me"},
                {"value": "no", "label": "No, that's not me"},
            ],
        )

    # Policy not found
    state["state_step"] = "no_policy_found"
    return set_response(
        state,
        response=(
            f"I couldn't find a policy with number **{policy_number}**.\n\n"
            "Would you like to continue as a guest? We can still file your claim and "
            "verify your policy later."
        ),
        pending_question="continue_guest",
        pending_field="guest_mode",
        input_type="yesno",
        options=[
            {"value": "yes", "label": "Yes, continue as guest"},
            {"value": "no", "label": "No, let me try again"},
        ],
    )


def _handle_personal_info_lookup(state: FNOLConversationState) -> FNOLConversationState:
    """Handle lookup by personal information."""
    phone = state.get("state_data", {}).get("holder_phone")
    name = state.get("state_data", {}).get("holder_name")
    zip_code = state.get("state_data", {}).get("holder_zip")

    # Simulate lookup (replace with actual service call)
    policy_data = _simulate_personal_lookup(phone, name, zip_code)

    if policy_data:
        state["policy_match"] = PolicyMatchData(
            status="pending",
            policy_id=policy_data.get("policy_id"),
            policy_number=policy_data.get("policy_number"),
            method="personal_info",
            confidence=0.9,
            holder_name=policy_data.get("holder_name"),
            vehicles=policy_data.get("vehicles", []),
            drivers=policy_data.get("drivers", []),
        )

        state["state_step"] = "awaiting_verification"

        holder_name = policy_data.get("holder_name", name)
        policy_number = policy_data.get("policy_number", "")
        return set_response(
            state,
            response=f"I found policy **{policy_number}** for **{holder_name}**. Is this correct?",
            pending_question="verify_identity",
            pending_field="identity_confirmed",
            input_type="yesno",
            options=[
                {"value": "yes", "label": "Yes, that's correct"},
                {"value": "no", "label": "No, that's not my policy"},
            ],
        )

    # Not found
    state["state_step"] = "no_policy_found"
    return set_response(
        state,
        response=(
            "I couldn't find a matching policy with that information.\n\n"
            "Would you like to continue as a guest? We can still file your claim and "
            "our team will help match it to your policy."
        ),
        pending_question="continue_guest",
        pending_field="guest_mode",
        input_type="yesno",
        options=[
            {"value": "yes", "label": "Yes, continue as guest"},
            {"value": "no", "label": "No, let me try again"},
        ],
    )


def _handle_policy_verification(state: FNOLConversationState) -> FNOLConversationState:
    """Handle policy verification step."""
    policy_match = state.get("policy_match", {})
    holder_name = policy_match.get("holder_name", "Unknown")

    state["state_step"] = "awaiting_verification"
    return set_response(
        state,
        response=f"I have your policy on file for **{holder_name}**. Is this correct?",
        pending_question="verify_identity",
        pending_field="identity_confirmed",
        input_type="yesno",
        options=[
            {"value": "yes", "label": "Yes, that's me"},
            {"value": "no", "label": "No, that's not me"},
        ],
    )


def _setup_guest_mode(state: FNOLConversationState) -> FNOLConversationState:
    """Set up guest mode and continue."""
    state["policy_match"] = PolicyMatchData(
        status="guest",
        policy_id=None,
        method="guest",
        confidence=0.0,
    )

    state = add_audit_event(
        state,
        action="guest_mode_activated",
        actor="user",
        field_changed="policy_match.status",
        data_after="guest",
    )

    state = transition_state(state, "INCIDENT_CORE", "initial")
    return state


# Utility functions

def extract_policy_number(text: str) -> Optional[str]:
    """Extract policy number from text."""
    # Common patterns: AUTO-123456, POL123456, A12345678
    patterns = [
        r'[A-Z]{2,4}[-]?\d{6,10}',
        r'[A-Z]\d{8,12}',
        r'\d{8,12}',
        r'AUTO[- ]?[A-Z0-9]+',  # Demo/Test format (matches AUTODEMO001)
    ]

    text_upper = text.upper().replace(" ", "").replace("-", "")

    for pattern in patterns:
        match = re.search(pattern, text_upper)
        if match:
            return match.group()

    return None


def extract_phone_number(text: str) -> Optional[str]:
    """Extract phone number from text."""
    # Remove non-digits
    digits = re.sub(r'\D', '', text)

    # Check for valid US phone (10 digits, optionally with 1 prefix)
    if len(digits) == 11 and digits[0] == '1':
        digits = digits[1:]
    if len(digits) == 10:
        return digits

    return None


def extract_zip_code(text: str) -> Optional[str]:
    """Extract ZIP code from text."""
    match = re.search(r'\b\d{5}(?:-\d{4})?\b', text)
    if match:
        return match.group()[:5]  # Return just 5 digits
    return None


def _simulate_policy_lookup(policy_number: str) -> Optional[dict]:
    """
    Simulate policy lookup by number.
    Replace with actual service call.
    """
    # For demo/testing, accept any policy starting with AUTO
    if policy_number.upper().startswith("AUTO"):
        return {
            "policy_id": "demo-policy-id",
            "policy_number": policy_number,
            "holder_name": "John Smith",
            "vehicles": [
                {
                    "vehicle_id": "v1",
                    "year": 2022,
                    "make": "Honda",
                    "model": "Accord",
                    "color": "Blue",
                    "vin": "1HGBH41JXMN109186",
                    "license_plate": "ABC1234",
                    "license_state": "TX",
                }
            ],
            "drivers": [
                {
                    "driver_id": "d1",
                    "first_name": "John",
                    "last_name": "Smith",
                    "is_primary": True,
                }
            ],
        }
    return None


def _simulate_personal_lookup(phone: str, name: str, zip_code: str) -> Optional[dict]:
    """
    Simulate policy lookup by personal info.
    Replace with actual service call.
    """
    # For demo, always return a match
    if phone and name:
        return {
            "policy_id": "demo-policy-id",
            "policy_number": "AUTO-DEMO-001",
            "holder_name": name,
            "vehicles": [
                {
                    "vehicle_id": "v1",
                    "year": 2021,
                    "make": "Toyota",
                    "model": "Camry",
                    "color": "Silver",
                }
            ],
            "drivers": [],
        }
    return None
