"""
Attempted Theft Playbook

Attempted vehicle theft with damage but vehicle not taken.
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class AttemptedTheftPlaybook(SimplePlaybook):
    """Playbook for attempted theft claims."""

    playbook_id = "attempted_theft"
    display_name = "Attempted Theft"
    description = "Attempted theft - vehicle damaged but not taken"
    category = "theft"
    priority = 30
    required_states = ["INCIDENT_CORE", "DAMAGE_EVIDENCE"]

    detection_keywords = [
        "attempted", "tried to steal", "break in", "break-in", "broken into",
        "forced entry", "damaged lock", "ignition damage", "hotwire",
        "window broken", "door pried", "steering column"
    ]

    detection_conditions = {
        "incident.loss_type": "theft",
    }

    triage_flags = ["attempted_theft", "comprehensive_claim"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect attempted theft scenario."""
        score = 0.0

        incident = state.get("incident", {})
        if incident.get("loss_type") == "theft":
            score += 0.3

        # Check for attempted theft keywords
        description = incident.get("description", "").lower()
        current_input = state.get("current_input", "").lower()
        all_text = f"{description} {current_input}"

        if any(kw in all_text for kw in cls.detection_keywords):
            score += 0.6

        # If theft but vehicle still present
        theft_type = incident.get("theft_type", "")
        if theft_type == "attempted":
            score += 0.7

        # Vehicle exists in state (not missing)
        vehicles = state.get("vehicles", [])
        if vehicles and incident.get("loss_type") == "theft":
            # Has vehicle info = attempted not complete theft
            score += 0.2

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get attempted theft specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="attempted_entry_method",
                state="INCIDENT_CORE",
                priority=30,
                question_text="How did they try to get into or steal the vehicle?",
                input_type=QuestionType.MULTISELECT,
                options=[
                    {"value": "window_broken", "label": "Broke a window"},
                    {"value": "door_forced", "label": "Forced door open/lock damaged"},
                    {"value": "ignition", "label": "Damaged ignition/steering column"},
                    {"value": "hotwire", "label": "Tried to hotwire"},
                    {"value": "key_fob", "label": "Electronic/key fob signal relay"},
                    {"value": "unknown", "label": "Not sure"},
                ],
                field="incident.entry_method",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="attempted_contents",
                state="INCIDENT_CORE",
                priority=35,
                question_text="Was anything stolen from inside the vehicle?",
                input_type=QuestionType.YESNO,
                field="incident.contents_stolen",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="attempted_police",
                state="INCIDENT_CORE",
                priority=40,
                question_text="Have you filed a police report?",
                help_text="Recommended for attempted theft.",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "yes", "label": "Yes"},
                    {"value": "no", "label": "No"},
                    {"value": "will", "label": "I will file one"},
                ],
                field="police_info.report_status",
                required=True,
            ))

        if current_state == "DAMAGE_EVIDENCE":
            questions.append(PlaybookQuestion(
                question_id="attempted_drivable",
                state="DAMAGE_EVIDENCE",
                priority=25,
                question_text="Is the vehicle drivable after the attempted theft?",
                input_type=QuestionType.YESNO,
                field="vehicle.drivable_after_attempt",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="attempted_secure",
                state="DAMAGE_EVIDENCE",
                priority=28,
                question_text="Is the vehicle currently secure (can it be locked)?",
                input_type=QuestionType.YESNO,
                field="vehicle.currently_secure",
                required=True,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate attempted theft data."""
        errors = []
        warnings = []

        incident = state.get("incident", {})

        # Recommend police report
        police_status = state.get("police_info", {}).get("report_status")
        if police_status == "no":
            warnings.append("Police report recommended for attempted theft")

        # If vehicle not secure, warn about risk
        vehicle_secure = state.get("vehicle", {}).get("currently_secure")
        if vehicle_secure == False:
            warnings.append("Vehicle may need to be secured to prevent further attempts")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Attempted theft specific triage flags."""
        flags = ["attempted_theft", "comprehensive_claim"]

        incident = state.get("incident", {})

        # Contents stolen adds complexity
        if incident.get("contents_stolen"):
            flags.append("contents_stolen")

        # Ignition damage may need special handling
        entry_methods = incident.get("entry_method", [])
        if isinstance(entry_methods, list) and "ignition" in entry_methods:
            flags.append("ignition_damage")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for attempted theft claim."""
        evidence = [
            {"evidence_type": "photo", "description": "Photos of forced entry damage"},
            {"evidence_type": "photo", "description": "Photos of interior damage"},
        ]

        incident = state.get("incident", {})
        entry_methods = incident.get("entry_method", [])

        if isinstance(entry_methods, list):
            if "window_broken" in entry_methods:
                evidence.append({
                    "evidence_type": "photo",
                    "description": "Photos of broken window"
                })
            if "ignition" in entry_methods:
                evidence.append({
                    "evidence_type": "photo",
                    "description": "Photos of ignition/steering column damage"
                })

        return evidence
