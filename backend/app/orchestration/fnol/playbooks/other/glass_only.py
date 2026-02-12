"""
Glass Only Playbook

Windshield or window damage only.
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class GlassOnlyPlaybook(SimplePlaybook):
    """Playbook for glass-only claims (STP candidate)."""

    playbook_id = "glass_only"
    display_name = "Glass Only"
    description = "Windshield or window damage only"
    category = "other"
    priority = 70  # Lower priority - often STP eligible
    required_states = ["INCIDENT_CORE", "DAMAGE_EVIDENCE"]

    detection_keywords = [
        "windshield", "window", "glass", "crack", "chip", "rock hit",
        "stone chip", "cracked windshield", "broken window", "shattered"
    ]

    detection_conditions = {
        "incident.loss_type": "glass",
    }

    triage_flags = ["glass_only", "comprehensive_claim", "stp_candidate"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect glass-only scenario."""
        score = 0.0

        incident = state.get("incident", {})
        if incident.get("loss_type") == "glass":
            score += 0.7

        description = incident.get("description", "").lower()
        if any(kw in description for kw in cls.detection_keywords):
            score += 0.4

        # Check if only glass damage reported
        damages = state.get("damages", [])
        if damages:
            glass_damages = [d for d in damages if d.get("damage_area") in ["windshield", "side_window", "glass"]]
            if len(glass_damages) == len(damages):
                score += 0.3

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get glass-only specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="glass_type",
                state="INCIDENT_CORE",
                priority=30,
                question_text="Which glass is damaged?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "windshield", "label": "Windshield"},
                    {"value": "rear_window", "label": "Rear window"},
                    {"value": "side_window", "label": "Side window"},
                    {"value": "sunroof", "label": "Sunroof/moonroof"},
                    {"value": "multiple", "label": "Multiple pieces of glass"},
                ],
                field="incident.glass_type",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="glass_damage_type",
                state="INCIDENT_CORE",
                priority=33,
                question_text="What type of damage is it?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "chip", "label": "Small chip"},
                    {"value": "crack", "label": "Crack"},
                    {"value": "shattered", "label": "Shattered/broken"},
                ],
                field="incident.glass_damage_type",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="glass_cause",
                state="INCIDENT_CORE",
                priority=36,
                question_text="What caused the glass damage?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "road_debris", "label": "Rock/debris from road"},
                    {"value": "unknown", "label": "Unknown"},
                    {"value": "weather", "label": "Weather (hail, etc.)"},
                    {"value": "vandalism", "label": "Vandalism"},
                    {"value": "collision", "label": "Collision/accident"},
                ],
                field="incident.glass_cause",
                required=True,
            ))

        if current_state == "DAMAGE_EVIDENCE":
            questions.append(PlaybookQuestion(
                question_id="glass_other_damage",
                state="DAMAGE_EVIDENCE",
                priority=20,
                question_text="Is there any other damage to the vehicle besides the glass?",
                input_type=QuestionType.YESNO,
                field="damage.other_damage_present",
                required=True,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate glass-only data."""
        errors = []
        warnings = []

        # If other damage present, may not qualify as glass-only
        if state.get("damage", {}).get("other_damage_present"):
            warnings.append("Other damage present - may not qualify for glass-only claim")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Glass-only specific triage flags."""
        flags = ["glass_only", "comprehensive_claim"]

        incident = state.get("incident", {})

        # Glass-only with photo is prime STP candidate
        evidence = state.get("evidence", [])
        if any(e.get("evidence_type") == "photo" for e in evidence):
            flags.append("stp_candidate")

        # Windshield chips are often repair vs replace
        if incident.get("glass_damage_type") == "chip":
            flags.append("repair_candidate")

        # Vandalism-caused glass needs police report
        if incident.get("glass_cause") == "vandalism":
            flags.append("vandalism")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for glass-only claim."""
        return [
            {"evidence_type": "photo", "description": "Photo of the damaged glass"},
            {"evidence_type": "photo", "description": "Close-up of the damage (chip/crack)"},
        ]
