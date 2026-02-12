"""
Uninsured/Underinsured Motorist Playbook

Collision where the other driver has no or insufficient insurance.
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class UninsuredPlaybook(SimplePlaybook):
    """Playbook for uninsured/underinsured motorist claims."""

    playbook_id = "uninsured"
    display_name = "Uninsured/Underinsured Motorist"
    description = "Collision where the other driver lacks adequate insurance"
    category = "collision"
    priority = 25
    required_states = ["INCIDENT_CORE", "THIRD_PARTIES"]

    detection_keywords = [
        "no insurance", "uninsured", "underinsured", "not insured",
        "doesn't have insurance", "no coverage", "lapsed", "expired insurance",
        "fake insurance", "invalid insurance", "minimum coverage"
    ]

    detection_conditions = {
        "incident.loss_type": "collision",
    }

    triage_flags = ["uninsured_motorist"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect uninsured motorist situation."""
        score = 0.0

        incident = state.get("incident", {})
        if incident.get("loss_type") == "collision":
            score += 0.2

        # Check for keywords
        description = incident.get("description", "").lower()
        current_input = state.get("current_input", "").lower()
        all_text = f"{description} {current_input}"

        if any(kw in all_text for kw in cls.detection_keywords):
            score += 0.6

        # Check third party insurance status
        parties = state.get("parties", [])
        for party in parties:
            insurance_status = party.get("insurance_status", "").lower()
            if insurance_status in ["none", "uninsured", "unknown", "expired"]:
                score += 0.7

        # Explicit flag
        if state.get("state_data", {}).get("other_driver_uninsured"):
            score += 0.8

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get uninsured motorist specific questions."""
        questions = []

        if current_state == "THIRD_PARTIES":
            questions.append(PlaybookQuestion(
                question_id="uninsured_status",
                state="THIRD_PARTIES",
                priority=40,
                question_text="What is the insurance status of the other driver?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "uninsured", "label": "No insurance"},
                    {"value": "expired", "label": "Expired insurance"},
                    {"value": "underinsured", "label": "Minimum/insufficient coverage"},
                    {"value": "unknown", "label": "Unknown - they didn't provide info"},
                    {"value": "valid", "label": "They have valid insurance"},
                ],
                field="third_parties.other_insurance_status",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="uninsured_verification",
                state="THIRD_PARTIES",
                priority=45,
                question_text="How did you find out about their insurance status?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "told_me", "label": "They told me"},
                    {"value": "card", "label": "Their insurance card was expired/fake"},
                    {"value": "police", "label": "Police verified"},
                    {"value": "carrier", "label": "Their insurance company confirmed"},
                    {"value": "assumed", "label": "I'm assuming based on the situation"},
                ],
                field="third_parties.insurance_verification_method",
                required=False,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate uninsured motorist data."""
        errors = []
        warnings = []

        # Should have third party information even if uninsured
        parties = state.get("parties", [])
        third_parties = [p for p in parties if p.get("role") in ["tp_driver"]]

        if len(third_parties) == 0:
            warnings.append("Other driver information not collected")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Uninsured motorist specific triage flags."""
        flags = ["uninsured_motorist"]

        # Check for UM/UIM coverage on policy
        policy = state.get("policy_match", {})
        # In real implementation, would check for UM/UIM coverage
        # For now, just flag for adjuster review

        flags.append("um_coverage_check_needed")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for uninsured motorist claim."""
        return [
            {"evidence_type": "photo", "description": "Photos of all vehicle damage"},
            {"evidence_type": "photo", "description": "Photo of other driver's license"},
            {"evidence_type": "photo", "description": "Photo of other vehicle's license plate"},
            {"evidence_type": "document", "description": "Police report"},
            {"evidence_type": "document", "description": "Copy of other driver's invalid/expired insurance card (if available)"},
        ]
