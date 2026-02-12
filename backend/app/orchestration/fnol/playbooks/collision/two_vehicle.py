"""
Two-Vehicle Collision Playbook

Standard collision between two vehicles.
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class TwoVehiclePlaybook(SimplePlaybook):
    """Playbook for standard two-vehicle collisions."""

    playbook_id = "two_vehicle"
    display_name = "Two-Vehicle Collision"
    description = "Standard collision involving two vehicles"
    category = "collision"
    priority = 50
    required_states = ["INCIDENT_CORE", "VEHICLE_DRIVER", "THIRD_PARTIES"]

    detection_keywords = [
        "hit", "collision", "crash", "accident", "rear-ended", "rear ended",
        "t-boned", "sideswiped", "sideswipe", "other car", "other vehicle",
        "their car", "another car", "other driver"
    ]

    detection_conditions = {
        "incident.loss_type": "collision",
    }

    triage_flags = ["standard_collision"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect two-vehicle collision."""
        score = 0.0

        incident = state.get("incident", {})
        if incident.get("loss_type") == "collision":
            score += 0.4

        vehicles = state.get("vehicles", [])
        # Exactly 2 vehicles suggests two-vehicle collision
        if len(vehicles) == 2:
            score += 0.5
        # Or state_data indicates two vehicles involved
        elif state.get("state_data", {}).get("vehicle_count") == 2:
            score += 0.5

        # Check for keywords
        description = incident.get("description", "").lower()
        if any(kw in description for kw in cls.detection_keywords):
            score += 0.2

        # Reduce score if hit-and-run indicators present
        if any(kw in description for kw in ["left", "fled", "ran", "unknown"]):
            score -= 0.3

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get two-vehicle specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="two_vehicle_impact_type",
                state="INCIDENT_CORE",
                priority=30,
                question_text="How did the vehicles collide?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "rear_end", "label": "Rear-end collision"},
                    {"value": "t_bone", "label": "T-bone/Side impact"},
                    {"value": "sideswipe", "label": "Sideswipe"},
                    {"value": "head_on", "label": "Head-on collision"},
                    {"value": "angle", "label": "Angle collision"},
                    {"value": "other", "label": "Other"},
                ],
                field="incident.impact_type",
                required=True,
            ))

        if current_state == "THIRD_PARTIES":
            questions.append(PlaybookQuestion(
                question_id="two_vehicle_fault",
                state="THIRD_PARTIES",
                priority=50,
                question_text="In your opinion, who was at fault for this collision?",
                help_text="This is just for our records - fault determination will be made during the claims process.",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "other_driver", "label": "The other driver"},
                    {"value": "me", "label": "I was at fault"},
                    {"value": "shared", "label": "Shared responsibility"},
                    {"value": "unsure", "label": "I'm not sure"},
                ],
                field="incident.fault_opinion",
                required=False,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate two-vehicle collision data."""
        errors = []
        warnings = []

        vehicles = state.get("vehicles", [])

        # Should have exactly 2 vehicles
        if len(vehicles) < 2:
            warnings.append("Other vehicle information not yet collected")

        # Should have at least basic third party info
        parties = state.get("parties", [])
        third_party_drivers = [p for p in parties if p.get("role") == "tp_driver"]
        if len(third_party_drivers) == 0:
            warnings.append("Other driver information not yet collected")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for two-vehicle collision."""
        return [
            {"evidence_type": "photo", "description": "Photos of damage to your vehicle"},
            {"evidence_type": "photo", "description": "Photos of damage to the other vehicle"},
            {"evidence_type": "photo", "description": "Photos of the accident scene"},
            {"evidence_type": "photo", "description": "Photo of the other driver's license plate"},
            {"evidence_type": "document", "description": "Police report (if available)"},
        ]
