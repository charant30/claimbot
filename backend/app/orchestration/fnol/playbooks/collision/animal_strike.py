"""
Animal Strike Playbook

Collision with an animal (deer, dog, etc.).
"""
from typing import Dict, List, Any
from app.orchestration.fnol.playbooks.base import (
    SimplePlaybook,
    PlaybookQuestion,
    ValidationResult,
    QuestionType,
)


class AnimalStrikePlaybook(SimplePlaybook):
    """Playbook for animal strike incidents."""

    playbook_id = "animal_strike"
    display_name = "Animal Strike"
    description = "Collision with an animal"
    category = "collision"
    priority = 55
    required_states = ["INCIDENT_CORE", "VEHICLE_DRIVER"]

    detection_keywords = [
        "deer", "animal", "dog", "cat", "elk", "moose", "raccoon",
        "hit a deer", "hit an animal", "struck an animal", "wildlife",
        "ran out", "jumped out", "came out of nowhere"
    ]

    detection_conditions = {
        "incident.loss_type": "collision",
    }

    triage_flags = ["animal_strike"]

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect animal strike incident."""
        score = 0.0

        incident = state.get("incident", {})
        if incident.get("loss_type") == "collision":
            score += 0.2

        # Check for animal keywords
        description = incident.get("description", "").lower()
        current_input = state.get("current_input", "").lower()
        all_text = f"{description} {current_input}"

        if any(kw in all_text for kw in cls.detection_keywords):
            score += 0.7

        # Explicit flag
        if state.get("state_data", {}).get("animal_strike"):
            score += 0.8

        return min(1.0, max(0.0, score))

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Get animal strike specific questions."""
        questions = []

        if current_state == "INCIDENT_CORE":
            questions.append(PlaybookQuestion(
                question_id="animal_type",
                state="INCIDENT_CORE",
                priority=30,
                question_text="What type of animal did you hit?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "deer", "label": "Deer"},
                    {"value": "moose", "label": "Moose/Elk"},
                    {"value": "dog", "label": "Dog"},
                    {"value": "cat", "label": "Cat"},
                    {"value": "bird", "label": "Bird"},
                    {"value": "small", "label": "Small animal (raccoon, possum, etc.)"},
                    {"value": "livestock", "label": "Livestock (cow, horse, etc.)"},
                    {"value": "other", "label": "Other/Unknown"},
                ],
                field="incident.animal_type",
                required=True,
            ))

            questions.append(PlaybookQuestion(
                question_id="animal_outcome",
                state="INCIDENT_CORE",
                priority=35,
                question_text="What happened to the animal?",
                input_type=QuestionType.SELECT,
                options=[
                    {"value": "fled", "label": "It ran away"},
                    {"value": "on_scene", "label": "It's still at the scene"},
                    {"value": "deceased", "label": "It didn't survive"},
                    {"value": "unknown", "label": "I don't know"},
                ],
                field="incident.animal_outcome",
                required=False,
            ))

            questions.append(PlaybookQuestion(
                question_id="animal_swerve",
                state="INCIDENT_CORE",
                priority=38,
                question_text="Did you swerve to avoid the animal?",
                help_text="This can affect whether the damage is considered collision or comprehensive coverage.",
                input_type=QuestionType.YESNO,
                field="incident.swerved_to_avoid",
                required=True,
            ))

        return questions

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate animal strike data."""
        errors = []
        warnings = []

        incident = state.get("incident", {})

        if not incident.get("animal_type"):
            warnings.append("Animal type not specified")

        # If swerved and hit something else, may need single-vehicle playbook too
        if incident.get("swerved_to_avoid") and incident.get("collision_object"):
            warnings.append("Review whether this is animal strike or single-vehicle collision")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Animal strike specific triage flags."""
        flags = ["animal_strike"]

        incident = state.get("incident", {})
        animal_type = incident.get("animal_type", "")

        # Large animals typically mean more damage
        if animal_type in ["deer", "moose", "livestock"]:
            flags.append("large_animal")

        # May be comprehensive claim if hit animal directly
        if not incident.get("swerved_to_avoid"):
            flags.append("comprehensive_eligible")

        # Livestock may involve third party (farmer)
        if animal_type == "livestock":
            flags.append("possible_third_party")

        return flags

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Get required evidence for animal strike."""
        evidence = [
            {"evidence_type": "photo", "description": "Photos of vehicle damage"},
            {"evidence_type": "photo", "description": "Photos of the accident scene"},
        ]

        incident = state.get("incident", {})

        if incident.get("animal_outcome") in ["on_scene", "deceased"]:
            evidence.append({
                "evidence_type": "photo",
                "description": "Photos showing the animal (for documentation)"
            })

        if incident.get("animal_type") == "livestock":
            evidence.append({
                "evidence_type": "document",
                "description": "Police report (recommended for livestock)"
            })

        return evidence
