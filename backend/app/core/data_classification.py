"""
Data classification and PII handling for ClaimBot.
Defines sensitivity levels and provides utilities for data protection.
"""

from enum import Enum
from typing import Any
import re


class DataClassification(Enum):
    """Data sensitivity classification levels."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"  # PII, PHI, financial data


# Field classifications for different data types
FIELD_CLASSIFICATIONS: dict[str, DataClassification] = {
    # User fields
    "email": DataClassification.CONFIDENTIAL,
    "password_hash": DataClassification.RESTRICTED,
    "phone": DataClassification.CONFIDENTIAL,
    "ssn": DataClassification.RESTRICTED,
    "date_of_birth": DataClassification.CONFIDENTIAL,
    
    # Policy fields
    "policy_number": DataClassification.INTERNAL,
    "premium_amount": DataClassification.CONFIDENTIAL,
    
    # Claim fields
    "claim_number": DataClassification.INTERNAL,
    "loss_amount": DataClassification.CONFIDENTIAL,
    "paid_amount": DataClassification.CONFIDENTIAL,
    "bank_account": DataClassification.RESTRICTED,
    "routing_number": DataClassification.RESTRICTED,
    
    # Medical fields (PHI)
    "diagnosis_code": DataClassification.RESTRICTED,
    "procedure_code": DataClassification.RESTRICTED,
    "provider_npi": DataClassification.INTERNAL,
    "medical_record": DataClassification.RESTRICTED,
}


# Regex patterns for detecting sensitive data
SENSITIVE_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
    "bank_account": re.compile(r"\b\d{8,17}\b"),
}


def get_field_classification(field_name: str) -> DataClassification:
    """Get the classification level for a field."""
    return FIELD_CLASSIFICATIONS.get(
        field_name.lower(), 
        DataClassification.INTERNAL
    )


def mask_value(value: str, classification: DataClassification) -> str:
    """Mask a value based on its classification."""
    if classification == DataClassification.PUBLIC:
        return value
    elif classification == DataClassification.INTERNAL:
        return value  # Visible internally
    elif classification == DataClassification.CONFIDENTIAL:
        # Show first and last characters
        if len(value) <= 4:
            return "*" * len(value)
        return f"{value[0]}{'*' * (len(value) - 2)}{value[-1]}"
    else:  # RESTRICTED
        return "*" * min(len(value), 8)


def detect_and_mask_pii(text: str) -> str:
    """Detect and mask PII in free-form text."""
    masked = text
    
    # Mask SSNs
    masked = SENSITIVE_PATTERNS["ssn"].sub("***-**-****", masked)
    
    # Mask credit cards
    masked = SENSITIVE_PATTERNS["credit_card"].sub("****-****-****-****", masked)
    
    # Mask emails (keep domain visible)
    def mask_email(match: re.Match) -> str:
        email = match.group()
        local, domain = email.rsplit("@", 1)
        return f"{local[0]}***@{domain}"
    masked = SENSITIVE_PATTERNS["email"].sub(mask_email, masked)
    
    # Mask phone numbers
    def mask_phone(match: re.Match) -> str:
        phone = match.group()
        return f"***-***-{phone[-4:]}"
    masked = SENSITIVE_PATTERNS["phone"].sub(mask_phone, masked)
    
    return masked


def sanitize_for_logging(data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a dictionary for safe logging."""
    sanitized = {}
    
    for key, value in data.items():
        classification = get_field_classification(key)
        
        if value is None:
            sanitized[key] = None
        elif isinstance(value, str):
            if classification in [DataClassification.CONFIDENTIAL, DataClassification.RESTRICTED]:
                sanitized[key] = mask_value(value, classification)
            else:
                sanitized[key] = value
        elif isinstance(value, dict):
            sanitized[key] = sanitize_for_logging(value)
        elif isinstance(value, list):
            sanitized[key] = [
                sanitize_for_logging(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value
    
    return sanitized


def classify_request_body(body: dict[str, Any]) -> DataClassification:
    """Determine the highest classification level in a request body."""
    max_classification = DataClassification.PUBLIC
    
    def check_dict(d: dict) -> DataClassification:
        nonlocal max_classification
        for key, value in d.items():
            field_class = get_field_classification(key)
            if field_class.value > max_classification.value:
                max_classification = field_class
            if isinstance(value, dict):
                check_dict(value)
        return max_classification
    
    return check_dict(body)
