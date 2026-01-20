"""
Tests for security features and data protection.
"""

import pytest
from app.core.data_classification import (
    get_field_classification,
    mask_value,
    detect_and_mask_pii,
    sanitize_for_logging,
    DataClassification,
)


class TestDataClassification:
    """Test data classification utilities."""
    
    def test_field_classification_email(self):
        """Test email is classified as confidential."""
        classification = get_field_classification("email")
        assert classification == DataClassification.CONFIDENTIAL
    
    def test_field_classification_ssn(self):
        """Test SSN is classified as restricted."""
        classification = get_field_classification("ssn")
        assert classification == DataClassification.RESTRICTED
    
    def test_field_classification_unknown(self):
        """Test unknown fields default to internal."""
        classification = get_field_classification("some_unknown_field")
        assert classification == DataClassification.INTERNAL


class TestDataMasking:
    """Test data masking functions."""
    
    def test_mask_confidential_value(self):
        """Test confidential value masking."""
        masked = mask_value("test@example.com", DataClassification.CONFIDENTIAL)
        assert masked[0] == "t"
        assert masked[-1] == "m"
        assert "*" in masked
    
    def test_mask_restricted_value(self):
        """Test restricted value is fully masked."""
        masked = mask_value("123-45-6789", DataClassification.RESTRICTED)
        assert "123" not in masked
        assert masked == "********"
    
    def test_mask_public_value(self):
        """Test public value is not masked."""
        original = "public info"
        masked = mask_value(original, DataClassification.PUBLIC)
        assert masked == original


class TestPIIDetection:
    """Test PII detection and masking in free text."""
    
    def test_detect_ssn_in_text(self):
        """Test SSN is detected and masked."""
        text = "My SSN is 123-45-6789 please process."
        masked = detect_and_mask_pii(text)
        assert "123-45-6789" not in masked
        assert "***-**-****" in masked
    
    def test_detect_credit_card(self):
        """Test credit card is detected and masked."""
        text = "Card number 4111-1111-1111-1111"
        masked = detect_and_mask_pii(text)
        assert "4111" not in masked
        assert "****" in masked
    
    def test_detect_email_in_text(self):
        """Test email partial masking in text."""
        text = "Email me at john.doe@example.com"
        masked = detect_and_mask_pii(text)
        assert "john.doe@example.com" not in masked
        assert "@example.com" in masked  # Domain preserved
    
    def test_detect_phone_in_text(self):
        """Test phone number partial masking."""
        text = "Call me at 555-123-4567"
        masked = detect_and_mask_pii(text)
        assert "555-123" not in masked
        assert "4567" in masked  # Last 4 preserved


class TestSanitizeForLogging:
    """Test dictionary sanitization for safe logging."""
    
    def test_sanitize_simple_dict(self):
        """Test basic dictionary sanitization."""
        data = {
            "email": "test@example.com",
            "name": "John Doe",
            "ssn": "123-45-6789",
        }
        sanitized = sanitize_for_logging(data)
        
        assert "test@example.com" not in str(sanitized)
        assert "123-45-6789" not in str(sanitized)
        assert sanitized["name"] == "John Doe"  # Name not classified
    
    def test_sanitize_nested_dict(self):
        """Test nested dictionary sanitization."""
        data = {
            "user": {
                "email": "nested@example.com",
                "password_hash": "secret_hash_value",
            }
        }
        sanitized = sanitize_for_logging(data)
        
        assert "nested@example.com" not in str(sanitized)
        assert "secret_hash_value" not in str(sanitized)
    
    def test_sanitize_preserves_structure(self):
        """Test sanitization preserves data structure."""
        data = {
            "items": [
                {"email": "a@b.com", "id": 1},
                {"email": "c@d.com", "id": 2},
            ]
        }
        sanitized = sanitize_for_logging(data)
        
        assert len(sanitized["items"]) == 2
        assert sanitized["items"][0]["id"] == 1
        assert sanitized["items"][1]["id"] == 2
