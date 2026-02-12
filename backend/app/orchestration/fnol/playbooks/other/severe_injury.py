"""
Severe Injury Playbook

Claims involving severe or fatal injuries.
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class SevereInjuryPlaybook(SimplePlaybook):
    """Playbook for severe/fatal injury claims."""

    playbook_id = "severe_injury"
    display_name = "Severe Injury"
    description = "Claim involving severe or fatal injuries"
    category = "other"
    priority = 5  # Highest priority
    required_states = ["INJURIES"]

    detection_keywords = [
        "fatal", "fatality", "death", "died", "dead", "critical",
        "hospitalized", "admitted", "icu", "intensive care", "surgery",
        "life-threatening", "serious injury", "severe"
    ]

    triage_flags = ["severe_injury", "emergency_priority", "immediate_escalation"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect severe injury scenario."""
        score = 0.0

        injuries = state.get("injuries", [])
        for injury in injuries:
            severity = injury.get("severity", "")
            if severity == "fatal":
                score += 1.0
            elif severity == "severe":
                score += 0.8
            elif injury.get("treatment_level") == "admitted":
                score += 0.7

        incident = state.get("incident", {})
        description = incident.get("description", "").lower()
        if any(kw in description for kw in cls.detection_keywords):
            score += 0.5

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get severe injury specific questions."""
        questions = []

        if current_state == "INJURIES":
            questions.append(PlaybookQuestion(
                question_id="severe_hospital_name",
                state="INJURIES",
                priority=10,
                question_text="Which hospital is the injured person at?",
                input_type=QuestionType.TEXT,
                field="injuries.hospital_name",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="severe_family_contact",
                state="INJURIES",
                priority=15,
                question_text="Is there a family member or representative we should contact?",
                input_type=QuestionType.TEXT,
                help_text="Name and phone number",
                field="injuries.family_contact",
                required=False,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate severe injury data."""
        errors = []
        warnings = []

        injuries = state.get("injuries", [])
        severe_injuries = [i for i in injuries if i.get("severity") in ["severe", "fatal"]]

        if severe_injuries and not state.get("injuries", {}).get("hospital_name"):
            warnings.append("Hospital information recommended for severe injuries")

        return ValidationResult(valid=True, errors=errors, warnings=warnings)

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Severe injury specific triage flags."""
        flags = ["severe_injury", "emergency_priority", "immediate_escalation"]

        injuries = state.get("injuries", [])
        for injury in injuries:
            if injury.get("severity") == "fatal":
                flags.append("fatality")
                break

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for severe injury claim."""
        return [
            {"evidence_type": "document", "description": "Police report"},
            {"evidence_type": "document", "description": "Medical records"},
            {"evidence_type": "document", "description": "Hospital admission records"},
        ]
