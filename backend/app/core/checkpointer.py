"""
LangGraph Checkpointer Configuration
Provides PostgreSQL-backed state persistence for conversations.
"""
from typing import Optional
from langgraph.checkpoint.postgres import PostgresSaver

from app.core.config import settings
from app.core.logging import logger


_checkpointer: Optional[PostgresSaver] = None


def get_checkpointer() -> PostgresSaver:
    """
    Get or create the PostgreSQL checkpointer for LangGraph.
    Uses the existing DATABASE_URL from settings.
    """
    global _checkpointer
    
    if _checkpointer is None:
        try:
            _checkpointer = PostgresSaver.from_conn_string(settings.DATABASE_URL)
            # Setup tables if they don't exist
            _checkpointer.setup()
            logger.info("PostgresSaver checkpointer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PostgresSaver: {e}")
            raise
    
    return _checkpointer


def cleanup_checkpointer():
    """Cleanup checkpointer connection on shutdown."""
    global _checkpointer
    if _checkpointer is not None:
        # PostgresSaver doesn't have explicit cleanup, but clear reference
        _checkpointer = None
        logger.info("Checkpointer cleaned up")
