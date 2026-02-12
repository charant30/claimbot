"""
Database utility functions with retry logic.
"""
import time
from typing import TypeVar, Callable, Any
from functools import wraps

from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, IntegrityError

from app.core.logging import logger


T = TypeVar("T")


class DatabaseOperationError(Exception):
    """Exception raised when a database operation fails after all retries."""

    def __init__(self, message: str, original_error: Exception = None):
        self.message = message
        self.original_error = original_error
        super().__init__(message)


def with_db_retry(
    max_retries: int = 3,
    retry_delay: float = 0.5,
    exponential_backoff: bool = True,
    rollback_on_error: bool = True,
):
    """
    Decorator for database operations with automatic retry logic.

    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries in seconds
        exponential_backoff: Whether to use exponential backoff
        rollback_on_error: Whether to rollback the session on error
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_error = None
            delay = retry_delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, IntegrityError) as e:
                    last_error = e

                    # Find db session in args/kwargs for rollback
                    if rollback_on_error:
                        db = kwargs.get("db")
                        if db is None:
                            for arg in args:
                                if isinstance(arg, Session):
                                    db = arg
                                    break
                        if db:
                            try:
                                db.rollback()
                            except Exception:
                                pass

                    if attempt < max_retries:
                        logger.warning(
                            f"Database operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        if exponential_backoff:
                            delay *= 2
                    else:
                        logger.error(
                            f"Database operation failed after {max_retries + 1} attempts: {e}"
                        )
                        raise DatabaseOperationError(
                            f"Database operation failed after {max_retries + 1} attempts",
                            original_error=e,
                        )
                except Exception as e:
                    # Non-retryable error
                    logger.error(f"Non-retryable database error: {e}")
                    raise

            # Should never reach here, but just in case
            raise DatabaseOperationError(
                "Database operation failed",
                original_error=last_error,
            )

        return wrapper
    return decorator


def update_claim_draft_with_retry(
    db: Session,
    claim_draft_id: str,
    updates: dict,
    max_retries: int = 3,
) -> bool:
    """
    Update a claim draft with retry logic.

    Args:
        db: Database session
        claim_draft_id: The claim draft ID to update
        updates: Dictionary of field updates
        max_retries: Maximum retry attempts

    Returns:
        True if update successful, False otherwise
    """
    from app.db.models import ClaimDraft

    delay = 0.5
    for attempt in range(max_retries + 1):
        try:
            claim_draft = db.query(ClaimDraft).filter(
                ClaimDraft.claim_draft_id == claim_draft_id
            ).first()

            if not claim_draft:
                logger.warning(f"Claim draft not found: {claim_draft_id}")
                return False

            # Apply updates
            for field, value in updates.items():
                if hasattr(claim_draft, field):
                    setattr(claim_draft, field, value)

            db.commit()
            return True

        except OperationalError as e:
            db.rollback()
            if attempt < max_retries:
                logger.warning(
                    f"Failed to update claim draft (attempt {attempt + 1}): {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
                delay *= 2
            else:
                logger.error(f"Failed to update claim draft after {max_retries + 1} attempts: {e}")
                return False

        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error updating claim draft: {e}")
            return False

    return False


def create_claim_draft_with_retry(
    db: Session,
    claim_draft,
    max_retries: int = 3,
) -> bool:
    """
    Create a claim draft with retry logic.

    Args:
        db: Database session
        claim_draft: The ClaimDraft model instance to create
        max_retries: Maximum retry attempts

    Returns:
        True if creation successful, False otherwise
    """
    delay = 0.5
    for attempt in range(max_retries + 1):
        try:
            db.add(claim_draft)
            db.commit()
            return True

        except IntegrityError as e:
            db.rollback()
            # Duplicate key - likely already exists
            logger.warning(f"Claim draft may already exist: {e}")
            return False

        except OperationalError as e:
            db.rollback()
            if attempt < max_retries:
                logger.warning(
                    f"Failed to create claim draft (attempt {attempt + 1}): {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
                delay *= 2
            else:
                logger.error(f"Failed to create claim draft after {max_retries + 1} attempts: {e}")
                return False

        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error creating claim draft: {e}")
            return False

    return False
