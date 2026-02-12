"""
Vandalism Playbook

Intentional damage to vehicle by a third party.
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class VandalismPlaybook(SimplePlaybook):
    """Playbook for vandalism claims."""

    playbook_id = "vandalism"
    display_name = "Vandalism"
    description = "Intentional damage to vehicle"
    category = "other"
    priority = 50
    required_states = ["INCIDENT_CORE", "DAMAGE_EVIDENCE"]

    detection_keywords = [
        "vandalized", "vandalism", "keyed", "scratched", "spray paint",
        "graffiti", "slashed", "tires slashed", "smashed", "broken into",
        "egged", "dented", "intentional", "someone damaged"
    ]

    detection_conditions = {
        "incident.loss_type": "vandalism",
    }

    triage_flags = ["vandalism", "comprehensive_claim"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect vandalism scenario."""
        score = 0.0

        incident = state.get("incident", {})
        if incident.get("loss_type") == "vandalism":
            score += 0.6

        description = incident.get("description", "").lower()
        if any(kw in description for kw in cls.detection_keywords):
            score += 0.5

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get vandalism specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="vandalism_type",
                state="INCIDENT_CORE",
                priority=30,
                question_text="What type of vandalism occurred?",
                input_type=QuestionType.MULTISELECT,
                options=[
                    {"value": "keyed", "label": "Keyed/scratched paint"},
                    {"value": "broken_glass", "label": "Broken windows/glass"},
                    {"value": "tires", "label": "Slashed tires"},
                    {"value": "dents", "label": "Dents/body damage"},
                    {"value": "spray_paint", "label": "Spray paint/graffiti"},
                    {"value": "other", "label": "Other"},
                ],
                field="incident.vandalism_type",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="vandalism_suspect",
                state="INCIDENT_CORE",
                priority=35,
                question_text="Do you know or suspect who did this?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "unknown", "label": "No, completely unknown"},
                    {"value": "suspect", "label": "Yes, I have a suspicion"},
                    {"value": "known", "label": "Yes, I know who did it"},
                ],
                field="incident.suspect_status",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="vandalism_police",
                state="INCIDENT_CORE",
                priority=40,
                question_text="Have you filed a police report?",
                input_type=QuestionType.YESNO,
                field="police_info.report_filed",
                required=True,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate vandalism data."""
        errors = []
        warnings = []

        police_info = state.get("police_info", {})
        if not police_info.get("report_filed"):
            warnings.append("Police report recommended for vandalism claims")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for vandalism claim."""
        return [
            {"evidence_type": "photo", "description": "Photos of all vandalism damage"},
            {"evidence_type": "photo", "description": "Wide shot showing location"},
            {"evidence_type": "document", "description": "Police report (recommended)"},
        ]
