"""
Base Playbook Abstract Class

Defines the interface for all FNOL scenario playbooks.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TypedDict
from enum import Enum


class QuestionType(str, Enum):
    """Types of questions a playbook can ask."""
    TEXT = "text"
    SELECT = "select"
    MULTISELECT = "multiselect"
    YESNO = "yesno"
    DATE = "date"
    TIME = "time"
    PHONE = "phone"
    PHOTO = "photo"


class PlaybookQuestion(TypedDict, total=False):
    """Structure for a playbook question."""
    question_id: str  # Unique identifier
    state: str  # Which state this question appears in
    priority: int  # Order within state (lower = earlier)
    question_text: str  # The question to ask
    help_text: Optional[str]  # Optional help text
    input_type: QuestionType  # Type of input expected
    options: Optional[List[Dict[str, str]]]  # For select/multiselect
    field: str  # Where to store the answer
    required: bool  # Whether answer is required
    condition: Optional[str]  # Condition expression for when to show
    validation: Optional[str]  # Validation rule name


class ValidationResult(TypedDict):
    """Result of playbook validation."""
    valid: bool
    errors: List[str]
    warnings: List[str]


class BasePlaybook(ABC):
    """
    Abstract base class for FNOL scenario playbooks.

    Each playbook represents a specific claim scenario (e.g., hit-and-run,
    hail damage, vehicle theft) and provides:
    - Detection logic to identify when it applies
    - Additional questions specific to the scenario
    - Validation rules for collected data
    - Triage flags that influence routing
    """

    # Class attributes to be defined by subclasses
    playbook_id: str = ""
    display_name: str = ""
    description: str = ""
    category: str = ""  # collision, weather, theft, other
    required_states: List[str] = []  # States this playbook needs to run through
    priority: int = 100  # Lower = higher priority for conflicting playbooks

    @classmethod
    @abstractmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """
        Detect if this playbook applies to the current claim.

        Analyzes the collected state data to determine relevance.

        Args:
            state: Current FNOL conversation state

        Returns:
            Confidence score 0.0-1.0 (0 = doesn't apply, 1 = definitely applies)
        """
        pass

    @classmethod
    @abstractmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """
        Get additional questions for the current state.

        Returns questions specific to this scenario that should be asked
        during the given state.

        Args:
            current_state: Current state in the flow (e.g., "INCIDENT_CORE")
            state: Current FNOL conversation state

        Returns:
            List of PlaybookQuestion dicts
        """
        pass

    @classmethod
    @abstractmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """
        Validate collected data for this scenario.

        Checks that all required scenario-specific data has been collected
        and is valid.

        Args:
            state: Current FNOL conversation state

        Returns:
            ValidationResult with valid flag, errors, and warnings
        """
        pass

    @classmethod
    @abstractmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """
        Get triage flags for this scenario.

        Returns flags that should influence the triage routing decision.

        Args:
            state: Current FNOL conversation state

        Returns:
            List of flag strings
        """
        pass

    @classmethod
    def get_summary_data(cls, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract scenario-specific data for claim summary.

        Override in subclasses to include relevant details in the claim summary.

        Args:
            state: Current FNOL conversation state

        Returns:
            Dict of key-value pairs for the summary
        """
        return {}

    @classmethod
    def get_required_evidence(cls, state: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Get list of required evidence for this scenario.

        Override in subclasses to specify what photos/documents are needed.

        Args:
            state: Current FNOL conversation state

        Returns:
            List of dicts with evidence_type and description
        """
        return []

    @classmethod
    def preprocess_input(cls, user_input: str, current_question: str) -> str:
        """
        Preprocess user input for scenario-specific handling.

        Override in subclasses if special input handling is needed.

        Args:
            user_input: Raw user input
            current_question: The question being answered

        Returns:
            Processed input string
        """
        return user_input

    @classmethod
    def get_next_question_id(
        cls,
        current_question_id: Optional[str],
        state: Dict[str, Any],
    ) -> Optional[str]:
        """
        Determine the next question to ask.

        Override in subclasses for complex question flow logic.

        Args:
            current_question_id: ID of the question just answered (None if starting)
            state: Current FNOL conversation state

        Returns:
            Next question ID or None if no more questions
        """
        return None


class SimplePlaybook(BasePlaybook):
    """
    Simplified playbook for scenarios with straightforward detection rules.

    Provides default implementations that can be configured via class attributes.
    """

    # Detection keywords - if any found, playbook may apply
    detection_keywords: List[str] = []

    # Detection conditions - dict of field: value that must match
    detection_conditions: Dict[str, Any] = {}

    # Questions to add - list of PlaybookQuestion
    questions: List[PlaybookQuestion] = []

    # Required fields for validation
    required_fields: List[str] = []

    # Triage flags to add when this playbook is active
    triage_flags: List[str] = []

    @classmethod
    def detect(cls, state: Dict[str, Any]) -> float:
        """Detect based on keywords and conditions."""
        score = 0.0

        # Check incident type/loss type conditions
        incident = state.get("incident", {})
        for field, expected in cls.detection_conditions.items():
            if "." in field:
                # Nested field like incident.loss_type
                parts = field.split(".")
                value = state
                for part in parts:
                    value = value.get(part, {}) if isinstance(value, dict) else None
            else:
                value = incident.get(field)

            if value == expected:
                score += 0.4

        # Check for keywords in description
        description = incident.get("description", "").lower()
        description += " " + state.get("current_input", "").lower()

        keyword_matches = sum(1 for kw in cls.detection_keywords if kw in description)
        if keyword_matches > 0:
            score += min(0.6, keyword_matches * 0.2)

        return min(1.0, score)

    @classmethod
    def get_questions(cls, current_state: str, state: Dict[str, Any]) -> List[PlaybookQuestion]:
        """Return questions for the current state."""
        return [q for q in cls.questions if q.get("state") == current_state]

    @classmethod
    def validate(cls, state: Dict[str, Any]) -> ValidationResult:
        """Validate required fields are present."""
        errors = []
        warnings = []

        for field in cls.required_fields:
            value = state
            for part in field.split("."):
                value = value.get(part, {}) if isinstance(value, dict) else None

            if value is None or value == "":
                errors.append(f"Missing required field: {field}")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    @classmethod
    def get_triage_flags(cls, state: Dict[str, Any]) -> List[str]:
        """Return configured triage flags."""
        return cls.triage_flags.copy()
