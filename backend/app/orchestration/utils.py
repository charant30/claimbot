"""
Utility functions for LLM response parsing and data extraction.
"""
import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional

from app.core.logging import logger


def extract_json_from_llm_response(content: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from LLM response, handling common formatting issues.

    Tries multiple strategies:
    1. Direct JSON parsing
    2. Markdown code block extraction (```json or ```)
    3. Find JSON object boundaries { ... }
    4. Handle trailing commas and common malformations

    Returns None if no valid JSON found (no warning logged - this is expected behavior
    when LLM doesn't return structured data).

    Args:
        content: Raw LLM response text

    Returns:
        Parsed dictionary or None if extraction fails
    """
    if not content:
        return None

    content = content.strip()

    # Strategy 1: Try direct parsing
    try:
        result = json.loads(content)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: Extract from markdown code blocks
    patterns = [
        r'```json\s*([\s\S]*?)\s*```',  # ```json ... ```
        r'```\s*([\s\S]*?)\s*```',       # ``` ... ```
    ]
    for pattern in patterns:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(1).strip())
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

    # Strategy 3: Find JSON object by braces
    start = content.find('{')
    if start != -1:
        # Find matching closing brace
        brace_count = 0
        end = -1
        in_string = False
        escape_next = False

        for i in range(start, len(content)):
            char = content[i]

            if escape_next:
                escape_next = False
                continue

            if char == '\\':
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break

        if end > start:
            json_str = content[start:end]
            try:
                result = json.loads(json_str)
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                # Strategy 4: Try fixing common issues
                fixed = _fix_common_json_issues(json_str)
                try:
                    result = json.loads(fixed)
                    if isinstance(result, dict):
                        return result
                except json.JSONDecodeError:
                    pass

    # No valid JSON found - return None (no warning needed)
    return None


def _fix_common_json_issues(json_str: str) -> str:
    """
    Fix common JSON formatting issues from LLMs.

    Handles:
    - Trailing commas before } or ]
    - Single quotes (in some cases)
    """
    # Remove trailing commas before } or ]
    fixed = re.sub(r',\s*([}\]])', r'\1', json_str)
    return fixed


def parse_monetary_value(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    """
    Parse a monetary value from various formats to Decimal.

    Handles:
    - Numbers: 1000, 1000.50
    - Strings: "$1,000", "1,000.50", "$2,500.00", "approximately $1000"
    - None/empty: returns default

    Args:
        value: The value to parse (int, float, str, Decimal, or None)
        default: Default value if parsing fails (default: Decimal("0"))

    Returns:
        Decimal representation of the monetary value
    """
    if value is None:
        return default

    # Already a Decimal
    if isinstance(value, Decimal):
        return value

    # Numeric types
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return default

    # String handling
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return default

        # Handle special values
        lower_cleaned = cleaned.lower()
        if lower_cleaned in ('n/a', 'na', 'none', 'null', 'unknown', '-'):
            return default

        # Find the first number pattern in the string
        # This handles "approximately $1,000.50" -> "1000.50"
        # Pattern: optional $, digits with optional commas, optional decimal with cents
        match = re.search(r'\$?\s*([\d,]+(?:\.\d{1,2})?)', cleaned)
        if match:
            numeric_str = match.group(1)
            # Remove commas
            numeric_str = numeric_str.replace(',', '')
            try:
                return Decimal(numeric_str)
            except InvalidOperation:
                pass

        # Try direct conversion as fallback (handles plain numbers like "1000")
        # Remove any non-numeric characters except decimal point
        digits_only = re.sub(r'[^\d.]', '', cleaned)
        if digits_only:
            # Handle multiple decimal points (keep only first)
            parts = digits_only.split('.')
            if len(parts) > 2:
                digits_only = parts[0] + '.' + ''.join(parts[1:])
            try:
                return Decimal(digits_only)
            except InvalidOperation:
                pass

    return default


def safe_get_decimal_field(
    collected_fields: Dict[str, Any],
    primary_key: str,
    fallback_key: str = None,
    default: Decimal = Decimal("0")
) -> Decimal:
    """
    Safely extract a decimal value from collected fields with fallback.

    Args:
        collected_fields: Dictionary of collected claim fields
        primary_key: Primary field key to look up
        fallback_key: Optional fallback field key if primary not found
        default: Default value if neither key found

    Returns:
        Parsed Decimal value
    """
    value = collected_fields.get(primary_key)
    if value is None and fallback_key:
        value = collected_fields.get(fallback_key)

    if value is None:
        return default

    return parse_monetary_value(value, default)
