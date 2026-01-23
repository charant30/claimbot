"""
LangFuse Observability Integration
Provides tracing and monitoring for LLM calls.
"""
from typing import Optional
from langfuse.callback import CallbackHandler

from app.core.config import settings
from app.core.logging import logger


_langfuse_handler: Optional[CallbackHandler] = None


def get_langfuse_handler() -> Optional[CallbackHandler]:
    """
    Get LangFuse callback handler for LLM observability.
    Returns None if LangFuse is not configured.
    """
    global _langfuse_handler
    
    # Check if LangFuse is configured
    if not getattr(settings, 'LANGFUSE_PUBLIC_KEY', None):
        return None
    
    if _langfuse_handler is None:
        try:
            _langfuse_handler = CallbackHandler(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=getattr(settings, 'LANGFUSE_HOST', 'https://cloud.langfuse.com'),
            )
            logger.info("LangFuse handler initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize LangFuse: {e}")
            return None
    
    return _langfuse_handler


def flush_langfuse():
    """Flush pending traces to LangFuse."""
    global _langfuse_handler
    if _langfuse_handler is not None:
        try:
            _langfuse_handler.flush()
        except Exception as e:
            logger.warning(f"Failed to flush LangFuse: {e}")
