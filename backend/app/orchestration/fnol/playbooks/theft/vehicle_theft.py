"""
Vehicle Theft Playbook

Complete vehicle theft scenario.
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class VehicleTheftPlaybook(SimplePlaybook):
    """Playbook for complete vehicle theft claims."""

    playbook_id = "vehicle_theft"
    display_name = "Vehicle Theft"
    description = "Complete theft of the vehicle"
    category = "theft"
    priority = 20  # High priority - requires police report
    required_states = ["INCIDENT_CORE", "VEHICLE_DRIVER"]

    detection_keywords = [
        "stolen", "theft", "stole", "missing", "gone", "taken",
        "car was stolen", "vehicle stolen", "disappeared"
    ]

    detection_conditions = {
        "incident.loss_type": "theft",
    }

    triage_flags = ["vehicle_theft", "comprehensive_claim", "police_report_required"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect vehicle theft scenario."""
        score = 0.0

        incident = state.get("incident", {})
        if incident.get("loss_type") == "theft":
            score += 0.5

        # Check for theft keywords
        description = incident.get("description", "").lower()
        current_input = state.get("current_input", "").lower()
        all_text = f"{description} {current_input}"

        if any(kw in all_text for kw in cls.detection_keywords):
            score += 0.5

        # Complete theft vs attempted
        if "whole" in all_text or "entire" in all_text or "completely" in all_text:
            score += 0.2

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get vehicle theft specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="theft_last_seen",
                state="INCIDENT_CORE",
                priority=25,
                question_text="When did you last see the vehicle?",
                input_type=QuestionType.TEXT,
                help_text="Approximate date and time",
                field="incident.theft_last_seen",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="theft_discovered",
                state="INCIDENT_CORE",
                priority=28,
                question_text="When did you discover it was missing?",
                input_type=QuestionType.TEXT,
                help_text="Approximate date and time",
                field="incident.theft_discovered",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="theft_location",
                state="INCIDENT_CORE",
                priority=30,
                question_text="Where was the vehicle when it was stolen?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "home", "label": "At home (driveway/garage)"},
                    {"value": "work", "label": "At work"},
                    {"value": "parking_lot", "label": "In a parking lot"},
                    {"value": "street", "label": "On the street"},
                    {"value": "other", "label": "Other location"},
                ],
                field="incident.theft_location_type",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="theft_keys",
                state="INCIDENT_CORE",
                priority=35,
                question_text="Where were the keys at the time of theft?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "with_me", "label": "With me"},
                    {"value": "in_vehicle", "label": "In the vehicle"},
                    {"value": "at_home", "label": "At home"},
                    {"value": "lost", "label": "Keys were lost/stolen too"},
                    {"value": "other", "label": "Other"},
                ],
                field="incident.keys_location",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="theft_police",
                state="INCIDENT_CORE",
                priority=40,
                question_text="Have you filed a police report?",
                help_text="A police report is required for theft claims.",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "yes", "label": "Yes, I have a report number"},
                    {"value": "pending", "label": "I've reported it, waiting for number"},
                    {"value": "no", "label": "Not yet"},
                ],
                field="police_info.report_status",
                required=True,
            ))

        if current_state == "VEHICLE_DRIVER":
            questions.append(PlaybookQuestion(
                question_id="theft_contents",
                state="VEHICLE_DRIVER",
                priority=45,
                question_text="Were there any valuable items in the vehicle?",
                help_text="Personal belongings may be covered separately.",
                input_type=QuestionType.YESNO,
                field="vehicle.valuable_contents",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="theft_tracking",
                state="VEHICLE_DRIVER",
                priority=48,
                question_text="Does the vehicle have any tracking devices (GPS, LoJack, OnStar)?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "yes", "label": "Yes"},
                    {"value": "no", "label": "No"},
                    {"value": "unknown", "label": "I'm not sure"},
                ],
                field="vehicle.has_tracking",
                required=True,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate vehicle theft data."""
        errors = []
        warnings = []

        incident = state.get("incident", {})
        police_info = state.get("police_info", {})

        # Police report is required
        if police_info.get("report_status") == "no":
            errors.append("Police report is required for theft claims")

        # Keys in vehicle is a red flag
        if incident.get("keys_location") == "in_vehicle":
            warnings.append("Keys left in vehicle - coverage may be affected")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Vehicle theft specific triage flags."""
        flags = ["vehicle_theft", "comprehensive_claim", "police_report_required"]

        incident = state.get("incident", {})

        # Keys in vehicle is a red flag for SIU
        if incident.get("keys_location") == "in_vehicle":
            flags.append("siu_review_keys")

        # Check for common fraud indicators
        if incident.get("theft_location_type") in ["home"]:
            # Home theft with keys is suspicious
            if incident.get("keys_location") == "in_vehicle":
                flags.append("siu_review_indicator")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for vehicle theft claim."""
        return [
            {"evidence_type": "document", "description": "Police report (required)"},
            {"evidence_type": "document", "description": "Vehicle title or registration"},
            {"evidence_type": "document", "description": "Both sets of keys (if available)"},
            {"evidence_type": "photo", "description": "Photo of spare key (to prove possession)"},
        ]
