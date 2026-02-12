"""
Commercial/Rideshare Playbook

Incidents involving commercial use or rideshare (Uber, Lyft).
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class CommercialRidesharePlaybook(SimplePlaybook):
    """Playbook for commercial/rideshare incidents."""

    playbook_id = "commercial_rideshare"
    display_name = "Commercial/Rideshare"
    description = "Incident during commercial or rideshare use"
    category = "other"
    priority = 20  # High priority - coverage implications
    required_states = ["INCIDENT_CORE", "VEHICLE_DRIVER"]

    detection_keywords = [
        "uber", "lyft", "rideshare", "ride share", "passenger", "delivery",
        "doordash", "grubhub", "instacart", "amazon", "commercial",
        "work", "business use", "for hire"
    ]

    triage_flags = ["commercial_use", "coverage_review_required"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect commercial/rideshare scenario."""
        score = 0.0

        incident = state.get("incident", {})
        description = incident.get("description", "").lower()
        if any(kw in description for kw in cls.detection_keywords):
            score += 0.7

        # Check use type in state
        use_type = state.get("vehicle", {}).get("use_at_time")
        if use_type in ["rideshare", "delivery", "commercial"]:
            score += 0.8

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get commercial/rideshare specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="commercial_type",
                state="INCIDENT_CORE",
                priority=20,
                question_text="What type of commercial/rideshare activity were you doing?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "uber", "label": "Uber/Lyft (with passenger)"},
                    {"value": "uber_waiting", "label": "Uber/Lyft (waiting for ride)"},
                    {"value": "delivery", "label": "Food delivery (DoorDash, etc.)"},
                    {"value": "package", "label": "Package delivery (Amazon, etc.)"},
                    {"value": "business", "label": "Business/work use"},
                    {"value": "other", "label": "Other commercial use"},
                ],
                field="incident.commercial_type",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="commercial_passenger",
                state="INCIDENT_CORE",
                priority=25,
                question_text="Did you have a paying passenger at the time?",
                input_type=QuestionType.YESNO,
                field="incident.had_passenger",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="commercial_app",
                state="INCIDENT_CORE",
                priority=28,
                question_text="Was the app active/logged in at the time of the incident?",
                input_type=QuestionType.YESNO,
                field="incident.app_active",
                required=True,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate commercial/rideshare data."""
        errors = []
        warnings = []

        warnings.append("Coverage may differ for commercial use - adjuster review required")

        return ValidationResult(valid=True, errors=errors, warnings=warnings)

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Commercial/rideshare specific triage flags."""
        flags = ["commercial_use", "coverage_review_required"]

        incident = state.get("incident", {})
        if incident.get("had_passenger"):
            flags.append("rideshare_with_passenger")
        if incident.get("app_active"):
            flags.append("app_active_at_time")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for commercial/rideshare claim."""
        return [
            {"evidence_type": "photo", "description": "Photos of damage"},
            {"evidence_type": "document", "description": "Rideshare app trip history/screenshot"},
            {"evidence_type": "document", "description": "Rideshare company incident report (if filed)"},
        ]
