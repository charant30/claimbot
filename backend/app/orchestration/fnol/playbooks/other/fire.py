"""
Fire Damage Playbook

Vehicle fire damage.
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class FirePlaybook(SimplePlaybook):
    """Playbook for fire damage claims."""

    playbook_id = "fire"
    display_name = "Fire Damage"
    description = "Vehicle fire damage"
    category = "other"
    priority = 25  # Higher priority - often total loss
    required_states = ["INCIDENT_CORE", "VEHICLE_DRIVER", "DAMAGE_EVIDENCE"]

    detection_keywords = [
        "fire", "burned", "burning", "flames", "smoke", "caught fire",
        "on fire", "engine fire", "electrical fire", "arson"
    ]

    detection_conditions = {
        "incident.loss_type": "fire",
    }

    triage_flags = ["fire_damage", "comprehensive_claim", "potential_total_loss"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect fire damage scenario."""
        score = 0.0

        incident = state.get("incident", {})
        if incident.get("loss_type") == "fire":
            score += 0.7

        description = incident.get("description", "").lower()
        if any(kw in description for kw in cls.detection_keywords):
            score += 0.5

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get fire-specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="fire_origin",
                state="INCIDENT_CORE",
                priority=30,
                question_text="Where did the fire start?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "engine", "label": "Engine compartment"},
                    {"value": "interior", "label": "Interior/cabin"},
                    {"value": "external", "label": "External fire (spread to vehicle)"},
                    {"value": "unknown", "label": "Unknown"},
                ],
                field="incident.fire_origin",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="fire_cause",
                state="INCIDENT_CORE",
                priority=33,
                question_text="Do you know what caused the fire?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "mechanical", "label": "Mechanical/electrical failure"},
                    {"value": "accident", "label": "Result of collision"},
                    {"value": "arson", "label": "Suspected arson"},
                    {"value": "wildfire", "label": "Wildfire/brush fire"},
                    {"value": "unknown", "label": "Unknown"},
                ],
                field="incident.fire_cause",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="fire_department",
                state="INCIDENT_CORE",
                priority=36,
                question_text="Was the fire department called?",
                input_type=QuestionType.YESNO,
                field="incident.fire_department_called",
                required=True,
            ))

        if current_state == "VEHICLE_DRIVER":
            questions.append(PlaybookQuestion(
                question_id="fire_extent",
                state="VEHICLE_DRIVER",
                priority=40,
                question_text="How much of the vehicle was damaged by fire?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "minor", "label": "Minor - small area"},
                    {"value": "moderate", "label": "Moderate - one section (engine or interior)"},
                    {"value": "severe", "label": "Severe - multiple areas"},
                    {"value": "total", "label": "Total loss - entire vehicle"},
                ],
                field="vehicle.fire_extent",
                required=True,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate fire damage data."""
        errors = []
        warnings = []

        incident = state.get("incident", {})

        if incident.get("fire_cause") == "arson":
            warnings.append("Suspected arson - police report required")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Fire-specific triage flags."""
        flags = ["fire_damage", "comprehensive_claim"]

        incident = state.get("incident", {})
        vehicle = state.get("vehicle", {})

        if vehicle.get("fire_extent") in ["severe", "total"]:
            flags.append("likely_total_loss")

        if incident.get("fire_cause") == "arson":
            flags.append("siu_review_arson")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for fire claim."""
        return [
            {"evidence_type": "photo", "description": "Photos of fire damage"},
            {"evidence_type": "document", "description": "Fire department report (if available)"},
            {"evidence_type": "document", "description": "Police report (if arson suspected)"},
        ]
