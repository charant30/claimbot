"""
Hail Damage Playbook

Vehicle damage from hailstorm.
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class HailPlaybook(SimplePlaybook):
    """Playbook for hail damage claims."""

    playbook_id = "hail"
    display_name = "Hail Damage"
    description = "Vehicle damage from a hailstorm"
    category = "weather"
    priority = 50
    required_states = ["INCIDENT_CORE", "DAMAGE_EVIDENCE"]

    detection_keywords = [
        "hail", "hailstorm", "hail storm", "hail damage", "dents from hail",
        "storm damage", "hail dents", "pockmarks"
    ]

    detection_conditions = {
        "incident.loss_type": "weather",
    }

    triage_flags = ["hail_damage", "comprehensive_claim"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect hail damage scenario."""
        score = 0.0

        incident = state.get("incident", {})
        if incident.get("loss_type") == "weather":
            score += 0.3

        # Check for hail keywords
        description = incident.get("description", "").lower()
        weather_type = incident.get("weather_type", "").lower()
        all_text = f"{description} {weather_type}"

        if any(kw in all_text for kw in cls.detection_keywords):
            score += 0.7

        if incident.get("weather_type") == "hail":
            score += 0.6

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get hail-specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="hail_size",
                state="INCIDENT_CORE",
                priority=30,
                question_text="Approximately how large was the hail?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "pea", "label": "Pea-sized (1/4 inch)"},
                    {"value": "marble", "label": "Marble-sized (1/2 inch)"},
                    {"value": "quarter", "label": "Quarter-sized (1 inch)"},
                    {"value": "golf_ball", "label": "Golf ball-sized (1.75 inches)"},
                    {"value": "larger", "label": "Larger than golf ball"},
                    {"value": "unknown", "label": "I'm not sure"},
                ],
                field="incident.hail_size",
                required=False,
            ))

            questions.append(PlaybookQuestion(
                question_id="hail_location",
                state="INCIDENT_CORE",
                priority=32,
                question_text="Where was your vehicle when the hail hit?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "parked_outside", "label": "Parked outside"},
                    {"value": "driving", "label": "I was driving"},
                    {"value": "parking_lot", "label": "In a parking lot"},
                    {"value": "other", "label": "Other"},
                ],
                field="incident.vehicle_location_during_hail",
                required=True,
            ))

        if current_state == "DAMAGE_EVIDENCE":
            questions.append(PlaybookQuestion(
                question_id="hail_glass_damage",
                state="DAMAGE_EVIDENCE",
                priority=20,
                question_text="Is there any glass damage (windshield, windows)?",
                input_type=QuestionType.YESNO,
                field="damage.glass_damage",
                required=True,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate hail damage data."""
        errors = []
        warnings = []

        incident = state.get("incident", {})

        # Hail claims often come in waves - note this for potential batch processing
        if not incident.get("date"):
            warnings.append("Incident date needed for hail storm verification")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Hail-specific triage flags."""
        flags = ["hail_damage", "comprehensive_claim"]

        incident = state.get("incident", {})

        # Large hail typically means more damage
        hail_size = incident.get("hail_size", "")
        if hail_size in ["golf_ball", "larger"]:
            flags.append("severe_hail")

        # Glass damage adds complexity
        damages = state.get("damages", [])
        if any("glass" in d.get("damage_area", "").lower() or "windshield" in d.get("damage_area", "").lower() for d in damages):
            flags.append("glass_damage")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for hail claim."""
        return [
            {"evidence_type": "photo", "description": "Photos of hail damage on hood/roof"},
            {"evidence_type": "photo", "description": "Close-up photos of individual dents"},
            {"evidence_type": "photo", "description": "Photos of any glass damage"},
            {"evidence_type": "photo", "description": "Wide shot showing overall damage pattern"},
        ]
