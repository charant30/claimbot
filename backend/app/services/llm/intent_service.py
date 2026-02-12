"""
Intent Detection Service

Classifies user input into predefined intents for the FNOL flow.
This is a bounded AI task - output is constrained to a fixed set of intents.

Valid intents:
- report_accident: User wants to report an incident
- provide_info: User is providing requested information
- confirm_yes: Affirmative response
- confirm_no: Negative response
- ask_question: User is asking a question
- request_human: User wants to speak to a human
- unclear: Intent cannot be determined
"""
from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass
import re
import os


class Intent(str, Enum):
    """Valid intents for FNOL flow."""
    REPORT_ACCIDENT = "report_accident"
    PROVIDE_INFO = "provide_info"
    CONFIRM_YES = "confirm_yes"
    CONFIRM_NO = "confirm_no"
    ASK_QUESTION = "ask_question"
    REQUEST_HUMAN = "request_human"
    UNCLEAR = "unclear"


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: Intent
    confidence: float
    secondary_intent: Optional[Intent] = None
    extracted_keywords: List[str] = None

    def to_dict(self) -> dict:
        return {
            "intent": self.intent.value,
            "confidence": self.confidence,
            "secondary_intent": self.secondary_intent.value if self.secondary_intent else None,
            "extracted_keywords": self.extracted_keywords or [],
        }


class IntentService:
    """
    Service for classifying user intent.

    Uses pattern matching for high-confidence cases and optionally
    falls back to LLM for ambiguous inputs.
    """

    # Pattern-based intent detection (fast path)
    YES_PATTERNS = [
        r"^y(es)?$", r"^yeah?$", r"^yep$", r"^yup$", r"^sure$",
        r"^ok(ay)?$", r"^correct$", r"^right$", r"^affirmative$",
        r"^that'?s (right|correct|me)$", r"^i (am|do|did|was|have)$",
        r"^definitely$", r"^absolutely$", r"^of course$",
    ]

    NO_PATTERNS = [
        r"^no?$", r"^nope$", r"^nah$", r"^negative$",
        r"^not (yet|now|really)$", r"^i (don'?t|didn'?t|wasn'?t|haven'?t)$",
        r"^never$", r"^none$",
    ]

    HUMAN_PATTERNS = [
        r"(speak|talk).*(human|person|agent|representative|someone)",
        r"(human|person|agent|representative)",
        r"(real|actual|live) (person|human|agent)",
        r"transfer me",
        r"get me (a |an )?(human|person|agent)",
        r"i (want|need) (a |an )?(human|person|agent)",
    ]

    QUESTION_PATTERNS = [
        r"^(what|when|where|why|how|who|which|can|could|would|should|is|are|do|does|did)\b",
        r"\?$",
        r"^(i )?don'?t (understand|know)",
        r"^(can|could) you (explain|tell|help)",
    ]

    REPORT_PATTERNS = [
        r"(report|file|make|submit).*(claim|accident|incident)",
        r"(had|was in|got in).*(accident|crash|collision|incident)",
        r"(car|vehicle).*(hit|damaged|stolen|broken)",
        r"(need|want) to (report|file|claim)",
    ]

    def __init__(self, use_llm_fallback: bool = False):
        """
        Initialize intent service.

        Args:
            use_llm_fallback: Whether to use LLM for ambiguous cases
        """
        self.use_llm_fallback = use_llm_fallback
        self._llm_client = None

    def classify(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> IntentResult:
        """
        Classify user input into an intent.

        Args:
            text: User's input text
            context: Optional context (current state, pending question, etc.)

        Returns:
            IntentResult with intent, confidence, and metadata
        """
        text_lower = text.lower().strip()
        context = context or {}

        # Empty input
        if not text_lower:
            return IntentResult(
                intent=Intent.UNCLEAR,
                confidence=1.0,
            )

        # Check for human request first (highest priority)
        if self._matches_patterns(text_lower, self.HUMAN_PATTERNS):
            return IntentResult(
                intent=Intent.REQUEST_HUMAN,
                confidence=0.95,
            )

        # Check for yes/no (high confidence patterns)
        if self._matches_patterns(text_lower, self.YES_PATTERNS):
            return IntentResult(
                intent=Intent.CONFIRM_YES,
                confidence=0.95,
            )

        if self._matches_patterns(text_lower, self.NO_PATTERNS):
            return IntentResult(
                intent=Intent.CONFIRM_NO,
                confidence=0.95,
            )

        # Check for questions
        if self._matches_patterns(text_lower, self.QUESTION_PATTERNS):
            return IntentResult(
                intent=Intent.ASK_QUESTION,
                confidence=0.85,
            )

        # Check for report intent
        if self._matches_patterns(text_lower, self.REPORT_PATTERNS):
            return IntentResult(
                intent=Intent.REPORT_ACCIDENT,
                confidence=0.9,
            )

        # Context-aware classification
        pending_question = context.get("pending_question")
        if pending_question:
            # If we're expecting a response, it's likely providing info
            return IntentResult(
                intent=Intent.PROVIDE_INFO,
                confidence=0.7,
            )

        # Check if input looks like data (contains numbers, dates, names)
        if self._looks_like_data(text):
            return IntentResult(
                intent=Intent.PROVIDE_INFO,
                confidence=0.75,
            )

        # LLM fallback for ambiguous cases
        if self.use_llm_fallback:
            return self._classify_with_llm(text, context)

        # Default to providing info if we have reasonable length
        if len(text_lower) > 10:
            return IntentResult(
                intent=Intent.PROVIDE_INFO,
                confidence=0.5,
            )

        return IntentResult(
            intent=Intent.UNCLEAR,
            confidence=0.5,
        )

    def _matches_patterns(self, text: str, patterns: List[str]) -> bool:
        """Check if text matches any of the patterns."""
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def _looks_like_data(self, text: str) -> bool:
        """Check if text looks like data input (dates, numbers, etc.)."""
        # Check for date patterns
        if re.search(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text):
            return True

        # Check for phone numbers
        if re.search(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', text):
            return True

        # Check for time patterns
        if re.search(r'\d{1,2}:\d{2}\s*(am|pm)?', text, re.IGNORECASE):
            return True

        # Check for addresses (contains numbers and state abbreviation or zip)
        if re.search(r'\d+.*\b[A-Z]{2}\b.*\d{5}', text, re.IGNORECASE):
            return True

        # Check for VIN
        if re.search(r'[A-HJ-NPR-Z0-9]{17}', text, re.IGNORECASE):
            return True

        # Check for license plates
        if re.search(r'\b[A-Z]{1,3}[-\s]?\d{1,4}[-\s]?[A-Z]{0,3}\b', text, re.IGNORECASE):
            return True

        return False

    def _classify_with_llm(
        self,
        text: str,
        context: Dict[str, Any],
    ) -> IntentResult:
        """
        Use LLM for intent classification (fallback).

        This is a bounded use - we constrain output to valid intents only.
        """
        try:
            from anthropic import Anthropic

            if self._llm_client is None:
                api_key = os.environ.get("ANTHROPIC_API_KEY")
                if not api_key:
                    return IntentResult(intent=Intent.UNCLEAR, confidence=0.3)
                self._llm_client = Anthropic(api_key=api_key)

            prompt = f"""Classify the following user input into exactly one of these intents:
- report_accident: User wants to report an incident
- provide_info: User is providing requested information
- confirm_yes: Affirmative response
- confirm_no: Negative response
- ask_question: User is asking a question
- request_human: User wants to speak to a human
- unclear: Cannot determine intent

User input: "{text}"
Current context: {context.get('pending_question', 'none')}

Respond with ONLY the intent name, nothing else."""

            response = self._llm_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=20,
                messages=[{"role": "user", "content": prompt}],
            )

            intent_str = response.content[0].text.strip().lower()

            # Map response to Intent enum
            intent_map = {
                "report_accident": Intent.REPORT_ACCIDENT,
                "provide_info": Intent.PROVIDE_INFO,
                "confirm_yes": Intent.CONFIRM_YES,
                "confirm_no": Intent.CONFIRM_NO,
                "ask_question": Intent.ASK_QUESTION,
                "request_human": Intent.REQUEST_HUMAN,
                "unclear": Intent.UNCLEAR,
            }

            intent = intent_map.get(intent_str, Intent.UNCLEAR)
            return IntentResult(intent=intent, confidence=0.8)

        except Exception as e:
            # Fallback on LLM error
            return IntentResult(intent=Intent.UNCLEAR, confidence=0.3)


# Singleton instance
_intent_service: Optional[IntentService] = None


def get_intent_service(use_llm: bool = False) -> IntentService:
    """Get or create intent service singleton."""
    global _intent_service
    if _intent_service is None:
        _intent_service = IntentService(use_llm_fallback=use_llm)
    return _intent_service
