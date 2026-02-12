"""
Multi-Vehicle Collision Playbook

Collision involving three or more vehicles.
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class MultiVehiclePlaybook(SimplePlaybook):
    """Playbook for multi-vehicle collisions (3+ vehicles)."""

    playbook_id = "multi_vehicle"
    display_name = "Multi-Vehicle Collision"
    description = "Collision involving three or more vehicles"
    category = "collision"
    priority = 30  # Higher priority due to complexity
    required_states = ["INCIDENT_CORE", "VEHICLE_DRIVER", "THIRD_PARTIES", "INJURIES"]

    detection_keywords = [
        "pile up", "pileup", "pile-up", "chain reaction", "multiple",
        "several cars", "three cars", "four cars", "many vehicles",
        "multiple vehicles", "3 cars", "4 cars", "5 cars"
    ]

    detection_conditions = {
        "incident.loss_type": "collision",
    }

    triage_flags = ["multi_vehicle", "complex_claim"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect multi-vehicle collision."""
        score = 0.0

        incident = state.get("incident", {})
        if incident.get("loss_type") == "collision":
            score += 0.2

        vehicles = state.get("vehicles", [])
        # 3+ vehicles strongly suggests multi-vehicle
        if len(vehicles) >= 3:
            score += 0.7

        # Check for keywords
        description = incident.get("description", "").lower()
        if any(kw in description for kw in cls.detection_keywords):
            score += 0.4

        # State data indicator
        vehicle_count = state.get("state_data", {}).get("vehicle_count", 0)
        if vehicle_count >= 3:
            score += 0.5

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get multi-vehicle specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="multi_vehicle_count",
                state="INCIDENT_CORE",
                priority=25,
                question_text="How many vehicles were involved in this collision?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "3", "label": "3 vehicles"},
                    {"value": "4", "label": "4 vehicles"},
                    {"value": "5", "label": "5 vehicles"},
                    {"value": "6+", "label": "6 or more vehicles"},
                ],
                field="incident.vehicle_count",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="multi_vehicle_position",
                state="INCIDENT_CORE",
                priority=28,
                question_text="What position was your vehicle in the collision sequence?",
                help_text="For example, if you were rear-ended then pushed into another car, you were in the middle.",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "first", "label": "First in chain (front)"},
                    {"value": "middle", "label": "Middle of chain"},
                    {"value": "last", "label": "Last in chain (rear)"},
                    {"value": "unsure", "label": "Not sure"},
                ],
                field="incident.vehicle_position",
                required=False,
            ))

        if current_state == "THIRD_PARTIES":
            questions.append(PlaybookQuestion(
                question_id="multi_vehicle_info_count",
                state="THIRD_PARTIES",
                priority=10,
                question_text="How many of the other drivers' information were you able to get?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "all", "label": "All of them"},
                    {"value": "some", "label": "Some of them"},
                    {"value": "none", "label": "None of them"},
                ],
                field="third_parties.info_collected",
                required=True,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate multi-vehicle collision data."""
        errors = []
        warnings = []

        incident = state.get("incident", {})
        vehicle_count = incident.get("vehicle_count")

        if not vehicle_count:
            warnings.append("Number of vehicles not specified")

        vehicles = state.get("vehicles", [])
        if len(vehicles) < 3:
            warnings.append("Full vehicle information not yet collected")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Multi-vehicle collisions always need adjuster review."""
        flags = ["multi_vehicle", "complex_claim"]

        # Add injury flag if applicable
        injuries = state.get("injuries", [])
        if any(i.get("severity") not in [None, "none"] for i in injuries):
            flags.append("multi_vehicle_with_injuries")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for multi-vehicle collision."""
        evidence = [
            {"evidence_type": "photo", "description": "Photos of your vehicle damage"},
            {"evidence_type": "photo", "description": "Wide shots showing all vehicles"},
            {"evidence_type": "photo", "description": "Photos of the accident scene"},
            {"evidence_type": "document", "description": "Police report (highly recommended)"},
        ]

        # Add evidence for each other vehicle if possible
        vehicles = state.get("vehicles", [])
        for i, v in enumerate(vehicles):
            if v.get("role") != "insured":
                evidence.append({
                    "evidence_type": "photo",
                    "description": f"Photos of vehicle #{i+1} damage and license plate"
                })

        return evidence
