"""
Hit and Run Playbook

Collision where the other driver fled the scene.
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class HitAndRunPlaybook(SimplePlaybook):
    """Playbook for hit-and-run incidents."""

    playbook_id = "hit_and_run"
    display_name = "Hit and Run"
    description = "Collision where the other driver fled the scene"
    category = "collision"
    priority = 20  # High priority due to need for police report
    required_states = ["INCIDENT_CORE", "VEHICLE_DRIVER", "THIRD_PARTIES"]

    detection_keywords = [
        "hit and run", "hit-and-run", "fled", "left the scene", "ran away",
        "drove off", "drove away", "didn't stop", "unknown driver",
        "never stopped", "took off", "sped away", "disappeared"
    ]

    detection_conditions = {
        "incident.loss_type": "collision",
    }

    triage_flags = ["hit_and_run", "police_report_required"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect hit-and-run incident."""
        score = 0.0

        incident = state.get("incident", {})
        if incident.get("loss_type") == "collision":
            score += 0.2

        # Check for keywords (strong indicator)
        description = incident.get("description", "").lower()
        current_input = state.get("current_input", "").lower()
        all_text = f"{description} {current_input}"

        if any(kw in all_text for kw in cls.detection_keywords):
            score += 0.7

        # Explicit flag in state
        if state.get("state_data", {}).get("hit_and_run"):
            score += 0.8

        # Third party marked as unknown/fled
        parties = state.get("parties", [])
        for party in parties:
            if party.get("is_unknown") or party.get("fled_scene"):
                score += 0.5

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get hit-and-run specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="hit_run_partial_info",
                state="INCIDENT_CORE",
                priority=30,
                question_text="Were you able to get any information about the other vehicle?",
                input_type=QuestionType.YESNO,
                field="incident.partial_info_obtained",
                required=True,
            ))

        if current_state == "THIRD_PARTIES":
            questions.append(PlaybookQuestion(
                question_id="hit_run_vehicle_desc",
                state="THIRD_PARTIES",
                priority=15,
                question_text="Can you describe the vehicle that hit you? (Make, model, color, any part of license plate)",
                input_type=QuestionType.TEXT,
                field="third_parties.fleeing_vehicle_description",
                required=False,
            ))

            questions.append(PlaybookQuestion(
                question_id="hit_run_direction",
                state="THIRD_PARTIES",
                priority=20,
                question_text="Which direction did the vehicle go after the collision?",
                input_type=QuestionType.TEXT,
                field="third_parties.flee_direction",
                required=False,
            ))

            questions.append(PlaybookQuestion(
                question_id="hit_run_witnesses",
                state="THIRD_PARTIES",
                priority=25,
                question_text="Were there any witnesses who might have seen more?",
                input_type=QuestionType.YESNO,
                field="third_parties.has_witnesses",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="hit_run_police",
                state="THIRD_PARTIES",
                priority=30,
                question_text="Have you filed a police report?",
                help_text="A police report is strongly recommended for hit-and-run claims.",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "yes", "label": "Yes, I filed a report"},
                    {"value": "will", "label": "I will file one"},
                    {"value": "no", "label": "No"},
                ],
                field="police_info.report_status",
                required=True,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate hit-and-run data."""
        errors = []
        warnings = []

        police_info = state.get("police_info", {})

        if not police_info.get("report_filed") and police_info.get("report_status") != "yes":
            warnings.append("Police report strongly recommended for hit-and-run claims")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Hit-and-run specific triage flags."""
        flags = ["hit_and_run"]

        police_info = state.get("police_info", {})
        if not police_info.get("report_filed"):
            flags.append("police_report_pending")
        else:
            flags.append("police_report_filed")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for hit-and-run."""
        return [
            {"evidence_type": "photo", "description": "Photos of all damage to your vehicle"},
            {"evidence_type": "photo", "description": "Photos of the accident scene"},
            {"evidence_type": "document", "description": "Police report (required)"},
            {"evidence_type": "photo", "description": "Photos of any debris left by other vehicle"},
            {"evidence_type": "document", "description": "Witness statements (if available)"},
        ]
