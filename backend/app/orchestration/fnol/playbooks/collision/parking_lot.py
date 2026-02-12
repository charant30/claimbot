"""
Parking Lot Incident Playbook

Collision that occurred in a parking lot or garage.
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class ParkingLotPlaybook(SimplePlaybook):
    """Playbook for parking lot incidents."""

    playbook_id = "parking_lot"
    display_name = "Parking Lot Incident"
    description = "Collision or damage in a parking lot or garage"
    category = "collision"
    priority = 60
    required_states = ["INCIDENT_CORE", "VEHICLE_DRIVER"]

    detection_keywords = [
        "parking lot", "parking garage", "parked", "parking structure",
        "while parked", "backing out", "backing up", "pulled out",
        "shopping center", "mall", "store parking", "parking space",
        "grocery store", "retail", "backed into"
    ]

    detection_conditions = {
        "incident.loss_type": "collision",
    }

    triage_flags = ["parking_lot"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect parking lot incident."""
        score = 0.0

        incident = state.get("incident", {})
        if incident.get("loss_type") == "collision":
            score += 0.2

        # Check for parking keywords
        description = incident.get("description", "").lower()
        location = incident.get("location_raw", "").lower()
        all_text = f"{description} {location}"

        keyword_matches = sum(1 for kw in cls.detection_keywords if kw in all_text)
        if keyword_matches > 0:
            score += min(0.7, keyword_matches * 0.25)

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get parking lot specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="parking_lot_type",
                state="INCIDENT_CORE",
                priority=32,
                question_text="What type of parking area was this?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "outdoor_lot", "label": "Outdoor parking lot"},
                    {"value": "garage", "label": "Parking garage"},
                    {"value": "street", "label": "Street parking"},
                    {"value": "private", "label": "Private property/driveway"},
                ],
                field="incident.parking_type",
                required=False,
            ))

            questions.append(PlaybookQuestion(
                question_id="parking_lot_situation",
                state="INCIDENT_CORE",
                priority=35,
                question_text="What was the situation when the collision occurred?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "parked_hit", "label": "My car was parked and was hit"},
                    {"value": "backing_out", "label": "I was backing out of a space"},
                    {"value": "other_backing", "label": "Another car backed into me"},
                    {"value": "both_moving", "label": "Both vehicles were moving"},
                    {"value": "door_ding", "label": "Door ding/shopping cart damage"},
                ],
                field="incident.parking_situation",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="parking_lot_other_party",
                state="INCIDENT_CORE",
                priority=38,
                question_text="Did you get the other party's information?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "yes", "label": "Yes, I have their info"},
                    {"value": "note", "label": "They left a note"},
                    {"value": "no", "label": "No, they left without leaving info"},
                    {"value": "unknown", "label": "I don't know who did it"},
                ],
                field="incident.other_party_info_status",
                required=True,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate parking lot incident data."""
        errors = []
        warnings = []

        incident = state.get("incident", {})

        # If other party info unknown, may be a hit-and-run
        info_status = incident.get("other_party_info_status")
        if info_status in ["no", "unknown"]:
            warnings.append("Consider filing police report for unknown other party")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Parking lot specific triage flags."""
        flags = ["parking_lot"]

        incident = state.get("incident", {})

        # May be STP candidate if minor damage
        damages = state.get("damages", [])
        total_estimate = sum(d.get("estimated_amount", 0) for d in damages)
        if total_estimate < 2000:
            flags.append("stp_candidate")

        # If other party unknown, treat like hit-and-run
        if incident.get("other_party_info_status") in ["no", "unknown"]:
            flags.append("hit_and_run")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for parking lot incident."""
        evidence = [
            {"evidence_type": "photo", "description": "Photos of your vehicle damage"},
            {"evidence_type": "photo", "description": "Wide shot of the parking area"},
        ]

        incident = state.get("incident", {})
        if incident.get("other_party_info_status") == "note":
            evidence.append({
                "evidence_type": "photo",
                "description": "Photo of the note left by other party"
            })

        if incident.get("other_party_info_status") in ["no", "unknown"]:
            evidence.append({
                "evidence_type": "document",
                "description": "Police report (recommended)"
            })

        return evidence
