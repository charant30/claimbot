"""
Wind/Tree Damage Playbook

Vehicle damage from wind, fallen trees, or debris.
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class WindTreePlaybook(SimplePlaybook):
    """Playbook for wind and tree damage claims."""

    playbook_id = "wind_tree"
    display_name = "Wind/Tree Damage"
    description = "Damage from wind, fallen trees, or debris"
    category = "weather"
    priority = 50
    required_states = ["INCIDENT_CORE", "DAMAGE_EVIDENCE"]

    detection_keywords = [
        "tree", "branch", "wind", "tornado", "hurricane", "storm",
        "fell on", "blown", "debris", "limb", "power line", "pole fell",
        "windstorm", "high winds"
    ]

    detection_conditions = {
        "incident.loss_type": "weather",
    }

    triage_flags = ["wind_tree_damage", "comprehensive_claim"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect wind/tree damage scenario."""
        score = 0.0

        incident = state.get("incident", {})
        if incident.get("loss_type") == "weather":
            score += 0.3

        # Check for wind/tree keywords
        description = incident.get("description", "").lower()
        weather_type = incident.get("weather_type", "").lower()
        all_text = f"{description} {weather_type}"

        if any(kw in all_text for kw in cls.detection_keywords):
            score += 0.7

        if incident.get("weather_type") in ["wind", "tree"]:
            score += 0.6

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get wind/tree specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="wind_damage_source",
                state="INCIDENT_CORE",
                priority=30,
                question_text="What caused the damage?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "tree", "label": "Fallen tree"},
                    {"value": "branch", "label": "Fallen branch/limb"},
                    {"value": "debris", "label": "Flying debris"},
                    {"value": "power_line", "label": "Power line/pole"},
                    {"value": "wind_direct", "label": "Direct wind damage"},
                    {"value": "other", "label": "Other"},
                ],
                field="incident.damage_source",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="wind_tree_location",
                state="INCIDENT_CORE",
                priority=33,
                question_text="Where was your vehicle when this happened?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "home", "label": "At home (driveway/property)"},
                    {"value": "parking_lot", "label": "In a parking lot"},
                    {"value": "street", "label": "Parked on the street"},
                    {"value": "driving", "label": "I was driving"},
                    {"value": "other", "label": "Other location"},
                ],
                field="incident.vehicle_location",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="wind_tree_removed",
                state="INCIDENT_CORE",
                priority=36,
                question_text="Has the tree/debris been removed from the vehicle?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "yes", "label": "Yes, it's been removed"},
                    {"value": "no", "label": "No, it's still on the vehicle"},
                    {"value": "partial", "label": "Partially removed"},
                ],
                field="incident.debris_status",
                required=True,
            ))

        if current_state == "DAMAGE_EVIDENCE":
            questions.append(PlaybookQuestion(
                question_id="wind_property_owner",
                state="DAMAGE_EVIDENCE",
                priority=50,
                question_text="Do you know who owns the property where the tree/debris came from?",
                help_text="This may be relevant if the damage was from a neighbor's tree.",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "my_property", "label": "It was on my property"},
                    {"value": "neighbor", "label": "Neighbor's property"},
                    {"value": "city", "label": "City/Public property"},
                    {"value": "unknown", "label": "I don't know"},
                ],
                field="incident.tree_owner",
                required=False,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate wind/tree damage data."""
        errors = []
        warnings = []

        incident = state.get("incident", {})

        # If debris still on vehicle, need to be careful about removal
        if incident.get("debris_status") == "no":
            warnings.append("Take photos before removing debris if possible")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Wind/tree specific triage flags."""
        flags = ["wind_tree_damage", "comprehensive_claim"]

        incident = state.get("incident", {})

        # Full tree typically means more damage
        if incident.get("damage_source") == "tree":
            flags.append("full_tree")

        # If from neighbor's property, may have subrogation potential
        if incident.get("tree_owner") in ["neighbor"]:
            flags.append("subrogation_potential")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for wind/tree claim."""
        evidence = [
            {"evidence_type": "photo", "description": "Photos of vehicle damage"},
            {"evidence_type": "photo", "description": "Photos showing the tree/debris (if still present)"},
            {"evidence_type": "photo", "description": "Wide shot showing vehicle and surroundings"},
        ]

        incident = state.get("incident", {})
        if incident.get("tree_owner") in ["neighbor", "city"]:
            evidence.append({
                "evidence_type": "photo",
                "description": "Photos showing where the tree/debris came from"
            })

        return evidence
