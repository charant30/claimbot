"""
Single-Vehicle Collision Playbook

Collision involving only one vehicle (e.g., ran off road, hit stationary object).
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class SingleVehiclePlaybook(SimplePlaybook):
    """Playbook for single-vehicle collisions."""

    playbook_id = "single_vehicle"
    display_name = "Single-Vehicle Collision"
    description = "Collision involving only one vehicle"
    category = "collision"
    priority = 50
    required_states = ["INCIDENT_CORE", "VEHICLE_DRIVER"]

    detection_keywords = [
        "hit a", "ran into", "crashed into", "slid", "lost control",
        "off the road", "off road", "ditch", "pole", "tree", "guardrail",
        "barrier", "fence", "wall", "curb", "pothole", "rolled",
        "flipped", "only my", "just my", "no other"
    ]

    detection_conditions = {
        "incident.loss_type": "collision",
    }

    triage_flags = ["single_vehicle"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect single-vehicle collision."""
        score = 0.0

        incident = state.get("incident", {})
        if incident.get("loss_type") == "collision":
            score += 0.3

        vehicles = state.get("vehicles", [])
        # Only 1 vehicle strongly suggests single-vehicle
        if len(vehicles) == 1:
            score += 0.4

        # Check for keywords
        description = incident.get("description", "").lower()
        if any(kw in description for kw in cls.detection_keywords):
            score += 0.4

        # Explicit indicator in state
        if state.get("state_data", {}).get("vehicle_count") == 1:
            score += 0.3

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get single-vehicle specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="single_vehicle_object",
                state="INCIDENT_CORE",
                priority=30,
                question_text="What did you hit or collide with?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "tree", "label": "Tree"},
                    {"value": "pole", "label": "Pole/Post"},
                    {"value": "guardrail", "label": "Guardrail/Barrier"},
                    {"value": "curb", "label": "Curb"},
                    {"value": "ditch", "label": "Ditch/Embankment"},
                    {"value": "building", "label": "Building/Structure"},
                    {"value": "pothole", "label": "Pothole"},
                    {"value": "rollover", "label": "Vehicle rolled over"},
                    {"value": "other", "label": "Other"},
                ],
                field="incident.collision_object",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="single_vehicle_cause",
                state="INCIDENT_CORE",
                priority=35,
                question_text="What caused you to lose control or collide?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "weather", "label": "Weather conditions (ice, rain, snow)"},
                    {"value": "road", "label": "Road conditions (debris, pothole)"},
                    {"value": "avoidance", "label": "Swerved to avoid something"},
                    {"value": "tire", "label": "Tire blowout"},
                    {"value": "mechanical", "label": "Mechanical failure"},
                    {"value": "distraction", "label": "Distraction"},
                    {"value": "other", "label": "Other/Not sure"},
                ],
                field="incident.collision_cause",
                required=False,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate single-vehicle collision data."""
        errors = []
        warnings = []

        incident = state.get("incident", {})

        if not incident.get("collision_object"):
            warnings.append("Object of collision not specified")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for single-vehicle collision."""
        return [
            {"evidence_type": "photo", "description": "Photos of vehicle damage"},
            {"evidence_type": "photo", "description": "Photos of the collision scene"},
            {"evidence_type": "photo", "description": "Photos of what was hit (tree, pole, etc.)"},
        ]
