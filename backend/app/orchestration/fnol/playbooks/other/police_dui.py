"""
Police/DUI Playbook

Incidents involving DUI, police action, or citations.
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class PoliceDuiPlaybook(SimplePlaybook):
    """Playbook for incidents involving DUI or police action."""

    playbook_id = "police_dui"
    display_name = "Police/DUI Involvement"
    description = "Incident involving DUI, arrest, or police action"
    category = "other"
    priority = 10  # Very high priority - coverage implications
    required_states = ["INCIDENT_CORE"]

    detection_keywords = [
        "dui", "dwi", "drunk", "drinking", "intoxicated", "arrested",
        "arrest", "citation", "ticket", "police", "charged", "breathalyzer",
        "blood test", "impaired", "under the influence"
    ]

    triage_flags = ["dui_involvement", "siu_review_required", "coverage_issue"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect DUI/police involvement scenario."""
        score = 0.0

        police_info = state.get("police_info", {})
        if police_info.get("dui_suspected") or police_info.get("dui_charged"):
            score += 0.9

        if police_info.get("arrest_made"):
            score += 0.5

        incident = state.get("incident", {})
        description = incident.get("description", "").lower()
        if any(kw in description for kw in cls.detection_keywords):
            score += 0.6

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get DUI/police specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="dui_arrest",
                state="INCIDENT_CORE",
                priority=20,
                question_text="Was anyone arrested at the scene?",
                input_type=QuestionType.YESNO,
                field="police_info.arrest_made",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="dui_charges",
                state="INCIDENT_CORE",
                priority=25,
                question_text="What charges, if any, were filed?",
                input_type=QuestionType.MULTISELECT,
                options=[
                    {"value": "dui", "label": "DUI/DWI"},
                    {"value": "reckless", "label": "Reckless driving"},
                    {"value": "hit_run", "label": "Hit and run"},
                    {"value": "speeding", "label": "Speeding"},
                    {"value": "other", "label": "Other"},
                    {"value": "none", "label": "No charges filed"},
                    {"value": "pending", "label": "Charges pending"},
                ],
                field="police_info.charges",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="dui_who",
                state="INCIDENT_CORE",
                priority=28,
                question_text="Who was involved in the arrest or citation?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "insured", "label": "The insured driver"},
                    {"value": "other_driver", "label": "The other driver"},
                    {"value": "both", "label": "Both drivers"},
                    {"value": "passenger", "label": "A passenger"},
                ],
                field="police_info.charged_party",
                required=True,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate DUI/police data."""
        errors = []
        warnings = []

        police_info = state.get("police_info", {})
        charges = police_info.get("charges", [])

        if isinstance(charges, list) and "dui" in charges:
            if police_info.get("charged_party") == "insured":
                warnings.append("DUI by insured driver may affect coverage")

        return ValidationResult(valid=True, errors=errors, warnings=warnings)

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """DUI/police specific triage flags."""
        flags = ["police_involvement"]

        police_info = state.get("police_info", {})
        charges = police_info.get("charges", [])

        if isinstance(charges, list) and "dui" in charges:
            flags.append("dui_involvement")
            if police_info.get("charged_party") == "insured":
                flags.append("insured_dui")
                flags.append("siu_review_required")
                flags.append("coverage_issue")

        if police_info.get("arrest_made"):
            flags.append("arrest_made")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for DUI/police claim."""
        return [
            {"evidence_type": "document", "description": "Police report (required)"},
            {"evidence_type": "document", "description": "Citation/arrest documents"},
            {"evidence_type": "document", "description": "Court documents (if applicable)"},
        ]
