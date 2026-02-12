"""
NEXT_STEPS State Handler

Provides confirmation and next steps after claim submission:
- Claim reference number
- Expected timeline
- Contact information
- Document submission instructions
- Follow-up actions
"""
from typing import Optional, List
from datetime import datetime, timedelta

from app.orchestration.fnol.state import FNOLConversationState
from app.orchestration.fnol.states.base import (
    add_audit_event,
    set_response,
)


def next_steps_node(state: FNOLConversationState) -> FNOLConversationState:
    """Process the NEXT_STEPS state."""
    step = state.get("state_step", "initial")

    # Step 1: Show confirmation and next steps
    if step == "initial":
        claim_number = state.get("claim_number", "N/A")
        triage = state.get("triage_result", {})
        route = triage.get("route", "adjuster")

        # Build next steps message
        message = build_next_steps_message(state, claim_number, route)

        state = add_audit_event(
            state,
            action="claim_submitted_confirmation",
            actor="system",
            data_after={
                "claim_number": claim_number,
                "route": route,
            },
        )

        state["state_step"] = "awaiting_questions"
        return set_response(
            state,
            response=message,
            pending_question="final_questions",
            pending_field="has_questions",
            input_type="select",
            options=[
                {"value": "done", "label": "I'm all set, thank you"},
                {"value": "questions", "label": "I have questions"},
                {"value": "documents", "label": "How do I submit documents?"},
                {"value": "timeline", "label": "What's the timeline?"},
            ],
        )

    # Step 2: Handle follow-up questions
    if step == "awaiting_questions":
        user_input = state.get("current_input", "").lower()

        if "done" in user_input or "set" in user_input or "thank" in user_input:
            state["is_complete"] = True
            state["state_step"] = "complete"

            state = add_audit_event(
                state,
                action="session_completed",
                actor="user",
            )

            return set_response(
                state,
                response=(
                    "You're welcome! Your claim has been submitted successfully. "
                    "We'll be in touch soon. Take care and drive safely!"
                ),
                pending_question=None,
            )

        if "document" in user_input or "upload" in user_input or "photo" in user_input:
            return set_response(
                state,
                response=get_document_instructions(state),
                pending_question="final_questions",
                pending_field="has_questions",
                input_type="select",
                options=[
                    {"value": "done", "label": "Got it, I'm all set"},
                    {"value": "questions", "label": "I have more questions"},
                ],
            )

        if "timeline" in user_input or "long" in user_input or "when" in user_input:
            return set_response(
                state,
                response=get_timeline_info(state),
                pending_question="final_questions",
                pending_field="has_questions",
                input_type="select",
                options=[
                    {"value": "done", "label": "Got it, I'm all set"},
                    {"value": "questions", "label": "I have more questions"},
                ],
            )

        if "question" in user_input:
            return set_response(
                state,
                response=(
                    "I'd be happy to help! What would you like to know about your claim?\n\n"
                    "You can also contact us directly:\n"
                    "• **Phone**: 1-800-CLAIMS (1-800-252-4670)\n"
                    "• **Email**: claims@example-insurance.com\n"
                    "• **Hours**: Monday-Friday, 8am-8pm EST"
                ),
                pending_question="specific_question",
                pending_field="question_text",
                input_type="text",
            )

        # General response
        state["is_complete"] = True
        state["state_step"] = "complete"
        return set_response(
            state,
            response=(
                "If you have any other questions, feel free to call us at 1-800-CLAIMS. "
                "Your claim has been submitted and you'll hear from us soon. Thank you!"
            ),
            pending_question=None,
        )

    # Step 3: Handle specific questions
    if step == "specific_question":
        # For specific questions, route to human if complex
        user_input = state.get("current_input", "").lower()

        # Check for common questions we can answer
        if "rental" in user_input or "car" in user_input:
            return set_response(
                state,
                response=get_rental_info(state),
                pending_question="final_questions",
                pending_field="has_questions",
                input_type="select",
                options=[
                    {"value": "done", "label": "Got it, I'm all set"},
                    {"value": "questions", "label": "I have more questions"},
                ],
            )

        if "tow" in user_input:
            return set_response(
                state,
                response=get_towing_info(state),
                pending_question="final_questions",
                pending_field="has_questions",
                input_type="select",
                options=[
                    {"value": "done", "label": "Got it, I'm all set"},
                    {"value": "questions", "label": "I have more questions"},
                ],
            )

        if "repair" in user_input or "shop" in user_input:
            return set_response(
                state,
                response=get_repair_info(state),
                pending_question="final_questions",
                pending_field="has_questions",
                input_type="select",
                options=[
                    {"value": "done", "label": "Got it, I'm all set"},
                    {"value": "questions", "label": "I have more questions"},
                ],
            )

        # Complex question - offer to connect with agent
        return set_response(
            state,
            response=(
                "That's a great question. For detailed answers about your specific situation, "
                "I recommend speaking with one of our claims representatives.\n\n"
                "• **Phone**: 1-800-CLAIMS (1-800-252-4670)\n"
                "• Available Monday-Friday, 8am-8pm EST\n\n"
                "Is there anything else I can help with?"
            ),
            pending_question="final_questions",
            pending_field="has_questions",
            input_type="select",
            options=[
                {"value": "done", "label": "No, I'm all set"},
                {"value": "questions", "label": "I have another question"},
            ],
        )

    # Mark as complete and return
    state["is_complete"] = True
    state["state_step"] = "complete"
    return state


def build_next_steps_message(
    state: FNOLConversationState,
    claim_number: str,
    route: str,
) -> str:
    """Build the confirmation and next steps message."""
    lines = [
        f"**Your claim has been submitted!**\n",
        f"**Claim Number: {claim_number}**\n",
        "Please save this number for your records.\n",
    ]

    # Route-specific messaging
    if route == "stp":
        lines.extend([
            "**What happens next:**",
            "Your claim qualifies for our expedited processing. "
            "You should receive a decision within 24-48 hours.\n",
        ])
    else:
        lines.extend([
            "**What happens next:**",
            "1. A claims adjuster will review your claim",
            "2. You'll receive a call within 1-2 business days",
            "3. The adjuster will guide you through the next steps\n",
        ])

    # Check if there are pending document requests
    evidence = state.get("evidence", [])
    pending_evidence = [e for e in evidence if e.get("upload_status") == "pending"]

    if pending_evidence:
        lines.extend([
            "**Documents to submit:**",
            "Please upload the following when available:",
        ])
        for ev in pending_evidence:
            subtype = ev.get("subtype", "document").replace("_", " ").title()
            lines.append(f"• {subtype} photos")
        lines.append("")

    # Vehicle not drivable - towing info
    vehicles = state.get("vehicles", [])
    non_drivable = [v for v in vehicles if v.get("is_drivable") == False]
    if non_drivable:
        lines.extend([
            "**Your vehicle:**",
            "Since your vehicle isn't drivable, our team will contact you "
            "to arrange towing and storage if needed.\n",
        ])

    # Contact information
    lines.extend([
        "**Questions?**",
        "• Phone: 1-800-CLAIMS",
        "• Email: claims@example-insurance.com",
        "• Online: www.example-insurance.com/claims\n",
    ])

    lines.append("Is there anything else you need help with?")

    return "\n".join(lines)


def get_document_instructions(state: FNOLConversationState) -> str:
    """Get instructions for submitting documents."""
    claim_number = state.get("claim_number", "your claim")

    return (
        f"**How to submit documents for {claim_number}:**\n\n"
        "**Option 1: Online Portal**\n"
        "• Log in to www.example-insurance.com/claims\n"
        "• Select your claim and click 'Upload Documents'\n"
        "• Accepted formats: JPG, PNG, PDF (max 10MB each)\n\n"
        "**Option 2: Mobile App**\n"
        "• Open the Example Insurance app\n"
        "• Go to 'My Claims' and select this claim\n"
        "• Tap 'Add Photos' to upload directly from your phone\n\n"
        "**Option 3: Email**\n"
        "• Send to: claims-docs@example-insurance.com\n"
        "• Include your claim number in the subject line\n\n"
        "**Helpful documents to submit:**\n"
        "• Photos of all damage (multiple angles)\n"
        "• Police report (if applicable)\n"
        "• Repair estimates\n"
        "• Medical records (for injury claims)\n"
        "• Witness contact information"
    )


def get_timeline_info(state: FNOLConversationState) -> str:
    """Get timeline information based on claim type."""
    triage = state.get("triage_result", {})
    route = triage.get("route", "adjuster")
    loss_type = state.get("incident", {}).get("loss_type", "collision")

    if route == "stp":
        return (
            "**Expected Timeline (Expedited Processing):**\n\n"
            "• **Decision**: Within 24-48 hours\n"
            "• **Payment**: 3-5 business days after approval\n\n"
            "You'll receive updates via email and text. "
            "If we need any additional information, we'll reach out promptly."
        )

    if loss_type == "theft":
        return (
            "**Expected Timeline (Theft Claim):**\n\n"
            "• **Initial contact**: Within 24 hours\n"
            "• **Investigation**: 7-14 days (includes police report review)\n"
            "• **Decision**: After investigation completes\n"
            "• **Settlement**: 5-10 business days after approval\n\n"
            "Please file a police report if you haven't already, "
            "as this is required for theft claims."
        )

    # Standard collision/other claims
    return (
        "**Expected Timeline:**\n\n"
        "• **Adjuster contact**: 1-2 business days\n"
        "• **Vehicle inspection**: Scheduled during adjuster call\n"
        "• **Estimate**: Within 3-5 days of inspection\n"
        "• **Repair authorization**: After estimate approval\n"
        "• **Payment**: Directly to repair shop or to you\n\n"
        "Total time varies based on repair complexity and parts availability. "
        "Your adjuster will keep you updated throughout the process."
    )


def get_rental_info(state: FNOLConversationState) -> str:
    """Get rental car information."""
    return (
        "**Rental Car Coverage:**\n\n"
        "If your policy includes rental reimbursement coverage, "
        "you may be eligible for a rental car while yours is being repaired.\n\n"
        "**To arrange a rental:**\n"
        "1. Your adjuster will confirm your coverage limits\n"
        "2. We have partnerships with Enterprise, Hertz, and National\n"
        "3. We can often bill directly, so you don't pay out of pocket\n\n"
        "**Typical coverage:**\n"
        "• $30-50 per day (varies by policy)\n"
        "• Up to 30 days maximum\n\n"
        "Your adjuster will discuss your specific coverage when they call."
    )


def get_towing_info(state: FNOLConversationState) -> str:
    """Get towing information."""
    return (
        "**Towing Assistance:**\n\n"
        "If your vehicle needs to be towed, we can help arrange it.\n\n"
        "**Options:**\n"
        "1. **24/7 Roadside**: Call 1-800-ROADSIDE\n"
        "2. **Use your own**: Keep the receipt for reimbursement\n\n"
        "**Coverage limits:**\n"
        "• Towing typically covered up to $100-150\n"
        "• Storage fees may be covered (check with adjuster)\n\n"
        "**Important:**\n"
        "If your vehicle is at a tow yard, fees can accumulate quickly. "
        "We recommend moving it to a preferred repair shop as soon as possible. "
        "Your adjuster can help coordinate this."
    )


def get_repair_info(state: FNOLConversationState) -> str:
    """Get repair shop information."""
    return (
        "**Getting Your Vehicle Repaired:**\n\n"
        "**Your options:**\n"
        "1. **Our network shops**: Pre-approved, guaranteed work, direct billing\n"
        "2. **Your preferred shop**: Get an estimate, we'll review and approve\n\n"
        "**Our Network Benefits:**\n"
        "• Lifetime warranty on repairs\n"
        "• Direct payment to shop\n"
        "• Quality-assured parts\n"
        "• Faster processing\n\n"
        "**To find a network shop:**\n"
        "• Visit: www.example-insurance.com/find-shop\n"
        "• Call: 1-800-REPAIRS\n"
        "• Ask your adjuster for recommendations\n\n"
        "You're free to choose any repair shop you prefer. "
        "If going with a non-network shop, please get an estimate before repairs begin."
    )
