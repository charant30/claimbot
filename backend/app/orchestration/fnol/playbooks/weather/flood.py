"""
Flood Damage Playbook

Vehicle damage from flooding.
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class FloodPlaybook(SimplePlaybook):
    """Playbook for flood damage claims."""

    playbook_id = "flood"
    display_name = "Flood Damage"
    description = "Vehicle damage from flooding"
    category = "weather"
    priority = 40  # Higher priority due to potential total loss
    required_states = ["INCIDENT_CORE", "VEHICLE_DRIVER", "DAMAGE_EVIDENCE"]

    detection_keywords = [
        "flood", "flooded", "flooding", "underwater", "submerged",
        "water damage", "flash flood", "rising water", "water level",
        "high water", "drove through water"
    ]

    detection_conditions = {
        "incident.loss_type": "weather",
    }

    triage_flags = ["flood_damage", "comprehensive_claim", "potential_total_loss"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect flood damage scenario."""
        score = 0.0

        incident = state.get("incident", {})
        if incident.get("loss_type") == "weather":
            score += 0.3

        # Check for flood keywords
        description = incident.get("description", "").lower()
        weather_type = incident.get("weather_type", "").lower()
        all_text = f"{description} {weather_type}"

        if any(kw in all_text for kw in cls.detection_keywords):
            score += 0.7

        if incident.get("weather_type") == "flood":
            score += 0.6

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get flood-specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="flood_water_level",
                state="INCIDENT_CORE",
                priority=30,
                question_text="How high did the water get on your vehicle?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "tires", "label": "Up to the tires/wheels"},
                    {"value": "doors", "label": "Up to the doors"},
                    {"value": "windows", "label": "Up to or above the windows"},
                    {"value": "submerged", "label": "Vehicle was fully submerged"},
                    {"value": "unknown", "label": "I'm not sure"},
                ],
                field="incident.water_level",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="flood_running",
                state="INCIDENT_CORE",
                priority=33,
                question_text="Was the vehicle running when it was flooded?",
                help_text="This is important for assessing potential engine damage.",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "running", "label": "Yes, engine was running"},
                    {"value": "off", "label": "No, engine was off"},
                    {"value": "stalled", "label": "Engine stalled in the water"},
                    {"value": "unknown", "label": "I don't know"},
                ],
                field="incident.engine_status_during_flood",
                required=True,
            ))

        if current_state == "VEHICLE_DRIVER":
            questions.append(PlaybookQuestion(
                question_id="flood_interior",
                state="VEHICLE_DRIVER",
                priority=40,
                question_text="Did water get inside the vehicle?",
                input_type=QuestionType.YESNO,
                field="vehicle.water_inside",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="flood_start",
                state="VEHICLE_DRIVER",
                priority=45,
                question_text="Have you tried to start the vehicle since the flooding?",
                help_text="Important: Do NOT try to start a flooded vehicle - this can cause additional damage.",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "no", "label": "No, I haven't tried"},
                    {"value": "yes_worked", "label": "Yes, it started"},
                    {"value": "yes_failed", "label": "Yes, but it won't start"},
                ],
                field="vehicle.attempted_start_after_flood",
                required=True,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate flood damage data."""
        errors = []
        warnings = []

        incident = state.get("incident", {})

        water_level = incident.get("water_level")
        if water_level in ["windows", "submerged"]:
            warnings.append("Vehicle may be a total loss - do not attempt to start")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Flood-specific triage flags."""
        flags = ["flood_damage", "comprehensive_claim"]

        incident = state.get("incident", {})

        # High water level often means total loss
        water_level = incident.get("water_level", "")
        if water_level in ["windows", "submerged"]:
            flags.append("likely_total_loss")
        elif water_level == "doors":
            flags.append("potential_total_loss")

        # Engine running during flood compounds damage
        if incident.get("engine_status_during_flood") in ["running", "stalled"]:
            flags.append("engine_damage_likely")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for flood claim."""
        return [
            {"evidence_type": "photo", "description": "Photos showing water damage exterior"},
            {"evidence_type": "photo", "description": "Photos of vehicle interior (water lines, mud)"},
            {"evidence_type": "photo", "description": "Photos of engine compartment"},
            {"evidence_type": "photo", "description": "Photos showing high water marks on vehicle"},
        ]
