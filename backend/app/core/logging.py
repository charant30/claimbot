"""
Logging configuration with field masking for sensitive data
"""
import logging
import re
from typing import Any

from app.core.config import settings


# Patterns to mask in logs
MASK_PATTERNS = [
    (r'"email":\s*"[^"]*"', '"email": "***@***"'),
    (r'"password":\s*"[^"]*"', '"password": "***"'),
    (r'"policy_number":\s*"[^"]*"', '"policy_number": "***"'),
    (r'"ssn":\s*"[^"]*"', '"ssn": "***-**-****"'),
    (r'"npi":\s*"[^"]*"', '"npi": "***"'),
]


class MaskingFormatter(logging.Formatter):
    """Custom formatter that masks sensitive fields."""
    
    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        for pattern, replacement in MASK_PATTERNS:
            message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)
        return message


def setup_logging() -> logging.Logger:
    """Configure application logging."""
    logger = logging.getLogger("claimbot")
    logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    
    # Format with masking
    formatter = MaskingFormatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    return logger


# Global logger instance
logger = setup_logging()


def log_audit_event(
    event_type: str,
    actor_id: str,
    actor_type: str,
    details: dict[str, Any],
) -> None:
    """Log an audit event (also persisted to database separately)."""
    logger.info(
        f"AUDIT: {event_type} | actor={actor_id} ({actor_type}) | details={details}"
    )
