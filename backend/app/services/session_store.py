"""
Session Store Service - Provides Redis-backed session storage with in-memory fallback.
"""
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

from app.core.config import settings
from app.core.logging import logger


class SessionStore(ABC):
    """Abstract base class for session storage."""

    @abstractmethod
    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a session by ID."""
        pass

    @abstractmethod
    def set(self, session_id: str, data: Dict[str, Any], ttl_hours: int = 24) -> None:
        """Set a session with optional TTL."""
        pass

    @abstractmethod
    def delete(self, session_id: str) -> bool:
        """Delete a session."""
        pass

    @abstractmethod
    def exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        pass


class InMemorySessionStore(SessionStore):
    """In-memory session store for development."""

    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._expiry: Dict[str, datetime] = {}

    def _cleanup_expired(self):
        """Remove expired sessions."""
        now = datetime.utcnow()
        expired = [k for k, v in self._expiry.items() if v < now]
        for key in expired:
            self._sessions.pop(key, None)
            self._expiry.pop(key, None)

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        self._cleanup_expired()
        return self._sessions.get(session_id)

    def set(self, session_id: str, data: Dict[str, Any], ttl_hours: int = 24) -> None:
        self._sessions[session_id] = data
        self._expiry[session_id] = datetime.utcnow() + timedelta(hours=ttl_hours)

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._expiry.pop(session_id, None)
            return True
        return False

    def exists(self, session_id: str) -> bool:
        self._cleanup_expired()
        return session_id in self._sessions

    def count(self) -> int:
        """Get the number of active sessions."""
        self._cleanup_expired()
        return len(self._sessions)

    def list_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all active sessions (for admin use)."""
        self._cleanup_expired()
        sessions = list(self._sessions.values())
        # Sort by created_at descending
        sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return sessions[:limit]


class RedisSessionStore(SessionStore):
    """Redis-backed session store for production."""

    def __init__(self, redis_url: str):
        import redis
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._prefix = "claimbot:session:"

    def _key(self, session_id: str) -> str:
        return f"{self._prefix}{session_id}"

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        data = self._redis.get(self._key(session_id))
        if data:
            return json.loads(data)
        return None

    def set(self, session_id: str, data: Dict[str, Any], ttl_hours: int = 24) -> None:
        self._redis.setex(
            self._key(session_id),
            timedelta(hours=ttl_hours),
            json.dumps(data, default=str)
        )

    def delete(self, session_id: str) -> bool:
        return self._redis.delete(self._key(session_id)) > 0

    def exists(self, session_id: str) -> bool:
        return self._redis.exists(self._key(session_id)) > 0

    def count(self) -> int:
        """Get approximate number of active sessions."""
        keys = self._redis.keys(f"{self._prefix}*")
        return len(keys)

    def list_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all active sessions (for admin use)."""
        keys = self._redis.keys(f"{self._prefix}*")
        sessions = []
        for key in keys[:limit * 2]:  # Fetch extra in case some fail
            data = self._redis.get(key)
            if data:
                try:
                    sessions.append(json.loads(data))
                except json.JSONDecodeError:
                    continue
            if len(sessions) >= limit:
                break
        # Sort by created_at descending
        sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return sessions[:limit]


# Singleton session store instance
_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """Get the session store instance (creates if needed)."""
    global _session_store

    if _session_store is not None:
        return _session_store

    # Try Redis first, fall back to in-memory
    if settings.REDIS_URL and settings.APP_ENV != "development":
        try:
            _session_store = RedisSessionStore(settings.REDIS_URL)
            # Test connection
            _session_store._redis.ping()
            logger.info("Using Redis session store")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis, using in-memory store: {e}")
            _session_store = InMemorySessionStore()
    else:
        logger.info("Using in-memory session store (development mode)")
        _session_store = InMemorySessionStore()

    return _session_store
