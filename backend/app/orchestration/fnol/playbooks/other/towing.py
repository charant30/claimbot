"""
Towing Playbook

Towing-related incidents (impound, unauthorized tow, damage during tow).
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class TowingPlaybook(SimplePlaybook):
    """Playbook for towing-related claims."""

    playbook_id = "towing"
    display_name = "Towing Incident"
    description = "Damage during towing or tow-related issues"
    category = "other"
    priority = 60
    required_states = ["INCIDENT_CORE", "VEHICLE_DRIVER"]

    detection_keywords = [
        "tow", "towed", "towing", "impound", "impounded", "tow truck",
        "tow yard", "damaged during tow", "tow company"
    ]

    triage_flags = ["towing_incident"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect towing-related scenario."""
        score = 0.0

        incident = state.get("incident", {})
        description = incident.get("description", "").lower()
        if any(kw in description for kw in cls.detection_keywords):
            score += 0.7

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get towing-specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="tow_type",
                state="INCIDENT_CORE",
                priority=30,
                question_text="What type of towing incident is this?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "damage", "label": "Vehicle damaged during towing"},
                    {"value": "impound", "label": "Vehicle impounded"},
                    {"value": "unauthorized", "label": "Unauthorized tow"},
                    {"value": "recovery", "label": "Breakdown/recovery tow"},
                ],
                field="incident.tow_type",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="tow_company",
                state="INCIDENT_CORE",
                priority=35,
                question_text="Do you know the tow company name?",
                input_type=QuestionType.TEXT,
                field="incident.tow_company",
                required=False,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate towing data."""
        errors = []
        warnings = []
        return ValidationResult(valid=True, errors=errors, warnings=warnings)

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Towing-specific triage flags."""
        flags = ["towing_incident"]

        incident = state.get("incident", {})
        if incident.get("tow_type") == "damage":
            flags.append("subrogation_potential")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for towing claim."""
        return [
            {"evidence_type": "photo", "description": "Photos of any damage"},
            {"evidence_type": "document", "description": "Tow receipt/documentation"},
        ]
