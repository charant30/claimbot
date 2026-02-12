"""
Out of State Playbook

Incidents occurring outside the policyholder's home state.
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class OutOfStatePlaybook(SimplePlaybook):
    """Playbook for out-of-state incidents."""

    playbook_id = "out_of_state"
    display_name = "Out of State"
    description = "Incident occurred outside home state"
    category = "other"
    priority = 55
    required_states = ["INCIDENT_CORE"]

    detection_keywords = [
        "out of state", "another state", "traveling", "vacation",
        "road trip", "visiting", "different state"
    ]

    triage_flags = ["out_of_state"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect out-of-state scenario."""
        score = 0.0

        incident = state.get("incident", {})

        # Check if location state differs from policy state
        incident_state = incident.get("location_state", "").upper()
        policy = state.get("policy_match", {})
        policy_state = policy.get("state", "").upper()

        if incident_state and policy_state and incident_state != policy_state:
            score += 0.8

        description = incident.get("description", "").lower()
        if any(kw in description for kw in cls.detection_keywords):
            score += 0.4

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get out-of-state specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="out_state_reason",
                state="INCIDENT_CORE",
                priority=40,
                question_text="Why were you in this state?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "vacation", "label": "Vacation/Travel"},
                    {"value": "business", "label": "Business trip"},
                    {"value": "visiting", "label": "Visiting family/friends"},
                    {"value": "moving", "label": "Moving/Relocating"},
                    {"value": "other", "label": "Other"},
                ],
                field="incident.out_of_state_reason",
                required=False,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate out-of-state data."""
        return ValidationResult(valid=True, errors=[], warnings=[])

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Out-of-state specific triage flags."""
        flags = ["out_of_state"]

        incident = state.get("incident", {})
        if incident.get("out_of_state_reason") == "moving":
            flags.append("potential_address_change")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for out-of-state claim."""
        return [
            {"evidence_type": "photo", "description": "Photos of damage"},
            {"evidence_type": "document", "description": "Police report (if applicable)"},
        ]
