"""
Rental Vehicle Playbook

Incidents involving a rental vehicle.
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class RentalPlaybook(SimplePlaybook):
    """Playbook for rental vehicle incidents."""

    playbook_id = "rental"
    display_name = "Rental Vehicle"
    description = "Incident involving a rental vehicle"
    category = "other"
    priority = 35
    required_states = ["INCIDENT_CORE", "VEHICLE_DRIVER"]

    detection_keywords = [
        "rental", "rented", "rental car", "hertz", "enterprise", "avis",
        "budget", "national", "alamo", "renting", "hired car"
    ]

    triage_flags = ["rental_vehicle"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect rental vehicle scenario."""
        score = 0.0

        incident = state.get("incident", {})
        description = incident.get("description", "").lower()
        if any(kw in description for kw in cls.detection_keywords):
            score += 0.7

        # Check vehicle ownership type
        vehicles = state.get("vehicles", [])
        for v in vehicles:
            if v.get("ownership_type") == "rental":
                score += 0.8

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get rental vehicle specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="rental_company",
                state="INCIDENT_CORE",
                priority=30,
                question_text="Which rental company did you rent from?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "enterprise", "label": "Enterprise"},
                    {"value": "hertz", "label": "Hertz"},
                    {"value": "avis", "label": "Avis"},
                    {"value": "budget", "label": "Budget"},
                    {"value": "national", "label": "National"},
                    {"value": "alamo", "label": "Alamo"},
                    {"value": "other", "label": "Other"},
                ],
                field="vehicle.rental_company",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="rental_insurance",
                state="INCIDENT_CORE",
                priority=35,
                question_text="Did you purchase insurance through the rental company?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "yes_full", "label": "Yes, full coverage"},
                    {"value": "yes_partial", "label": "Yes, partial coverage"},
                    {"value": "no", "label": "No, using my own insurance"},
                    {"value": "unsure", "label": "Not sure"},
                ],
                field="vehicle.rental_insurance",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="rental_reported",
                state="INCIDENT_CORE",
                priority=38,
                question_text="Have you reported this to the rental company?",
                input_type=QuestionType.YESNO,
                field="vehicle.rental_notified",
                required=True,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate rental vehicle data."""
        errors = []
        warnings = []

        vehicle = state.get("vehicle", {})
        if not vehicle.get("rental_notified"):
            warnings.append("Please notify the rental company of the incident")

        return ValidationResult(valid=True, errors=errors, warnings=warnings)

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Rental vehicle specific triage flags."""
        flags = ["rental_vehicle"]

        vehicle = state.get("vehicle", {})
        if vehicle.get("rental_insurance") in ["yes_full", "yes_partial"]:
            flags.append("rental_insurance_active")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for rental vehicle claim."""
        return [
            {"evidence_type": "photo", "description": "Photos of damage"},
            {"evidence_type": "document", "description": "Rental agreement"},
            {"evidence_type": "document", "description": "Rental company incident report"},
        ]
