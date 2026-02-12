"""
Injury Playbook

Claims involving injuries (non-severe).
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class InjuryPlaybook(SimplePlaybook):
    """Playbook for injury claims (minor to moderate)."""

    playbook_id = "injury"
    display_name = "Injury Claim"
    description = "Claim involving injuries"
    category = "other"
    priority = 25
    required_states = ["INJURIES"]

    detection_keywords = [
        "hurt", "injured", "injury", "pain", "hospital", "doctor",
        "medical", "treatment", "sore", "ache", "whiplash"
    ]

    triage_flags = ["injury_claim", "adjuster_required"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect injury scenario."""
        score = 0.0

        injuries = state.get("injuries", [])
        injury_count = len([i for i in injuries if i.get("severity") not in [None, "none"]])

        if injury_count > 0:
            score += 0.8

        incident = state.get("incident", {})
        description = incident.get("description", "").lower()
        if any(kw in description for kw in cls.detection_keywords):
            score += 0.3

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get injury-specific questions."""
        questions = []

        if current_state == "INJURIES":
            questions.append(PlaybookQuestion(
                question_id="injury_treatment_sought",
                state="INJURIES",
                priority=30,
                question_text="Has medical treatment been sought?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "yes_er", "label": "Yes, at emergency room"},
                    {"value": "yes_urgent", "label": "Yes, at urgent care"},
                    {"value": "yes_doctor", "label": "Yes, at doctor's office"},
                    {"value": "planned", "label": "Planning to see a doctor"},
                    {"value": "no", "label": "No treatment needed"},
                ],
                field="injuries.treatment_sought",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="injury_ongoing",
                state="INJURIES",
                priority=35,
                question_text="Is treatment ongoing?",
                input_type=QuestionType.YESNO,
                field="injuries.treatment_ongoing",
                required=True,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate injury data."""
        errors = []
        warnings = []

        injuries = state.get("injuries", [])
        if not injuries:
            warnings.append("Injury details not fully captured")

        return ValidationResult(valid=True, errors=errors, warnings=warnings)

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Injury-specific triage flags."""
        flags = ["injury_claim", "adjuster_required"]

        injuries_data = state.get("injuries", {})
        if injuries_data.get("treatment_ongoing"):
            flags.append("treatment_ongoing")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for injury claim."""
        return [
            {"evidence_type": "document", "description": "Medical records/bills"},
            {"evidence_type": "document", "description": "Police report"},
        ]
