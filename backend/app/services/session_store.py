"""
Session Store Service - Provides database, Redis-backed session storage with in-memory fallback.
"""
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

from app.core.config import settings
from app.core.logging import logger

# Max size of state_data we will persist to DB (avoid "cannot allocate memory for output buffer")
MAX_STATE_DATA_BYTES = 2 * 1024 * 1024  # 2 MB
# Max messages to keep when trimming (keeps recent conversation for transcripts)
MAX_MESSAGES_IN_STATE = 500


# Max chars per message content when trimming (avoid huge payloads)
MAX_MESSAGE_CONTENT_CHARS = 8000


def _trim_state_for_persistence(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Ensure state_data is within size limit. Never serializes the full state to check size;
    trims by message count and content length first to avoid OOM on bloated sessions.
    Returns a trimmed copy, or None to skip DB persist if still too large / serialization fails.
    """
    out = dict(data)
    messages = out.get("messages")
    if not isinstance(messages, list):
        messages = []

    # 1) Trim to last N messages without ever serializing the full blob
    if len(messages) > MAX_MESSAGES_IN_STATE:
        messages = messages[-MAX_MESSAGES_IN_STATE:]
        out["messages"] = messages
        logger.info(
            "Session state trimmed to last %s messages for persistence",
            MAX_MESSAGES_IN_STATE,
        )

    # 2) Truncate large message content so serialization stays bounded
    trimmed = []
    for m in messages:
        t = dict(m)
        content = t.get("content")
        if isinstance(content, str) and len(content) > MAX_MESSAGE_CONTENT_CHARS:
            t["content"] = content[:MAX_MESSAGE_CONTENT_CHARS] + "\n...[truncated]"
        trimmed.append(t)
    out["messages"] = trimmed

    # 3) Now safe to serialize and check size
    try:
        payload = json.dumps(out, default=str)
        size = len(payload.encode("utf-8"))
        if size > MAX_STATE_DATA_BYTES:
            logger.warning(
                "Session state still %s bytes after trim (max %s); skipping DB persist",
                size,
                MAX_STATE_DATA_BYTES,
            )
            return None  # Caller will skip persist when None
        return out
    except (TypeError, ValueError, MemoryError) as e:
        logger.warning("Could not serialize trimmed session state: %s", e)
        return None


def deduplicate_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Return messages with duplicates removed, preserving order.
    Deduplicates by message_id when present, otherwise by (role, content, created_at).
    Used so admin/Celest show each message once even if storage has duplicates (e.g. retries).
    """
    if not messages:
        return []
    seen = set()
    out = []
    for m in messages:
        mid = m.get("message_id")
        if mid:
            key = ("id", mid)
        else:
            key = ("content", m.get("role"), m.get("content", ""), m.get("created_at", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(m)
    return out


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

    @abstractmethod
    def list_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List all active sessions (for admin use)."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Get the number of active sessions."""
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

    def list_all(self, limit: int = 100, include_completed: bool = False) -> List[Dict[str, Any]]:
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

    def list_all(self, limit: int = 100, include_completed: bool = False) -> List[Dict[str, Any]]:
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


class DatabaseSessionStore(SessionStore):
    """Database-backed session store with in-memory cache for performance."""

    def __init__(self):
        # Use in-memory cache for fast access
        self._cache = InMemorySessionStore()

    def _get_db(self):
        """Get database session."""
        from app.db.session import get_db
        return next(get_db())

    def _persist_to_db(self, session_id: str, data: Dict[str, Any]) -> None:
        """Persist session data to database. Trims state if over size limit to avoid DB buffer errors."""
        try:
            from app.db.models import Session, SessionType, SessionStatus, User

            trimmed = _trim_state_for_persistence(data)
            if trimmed is None:
                return
            data = trimmed
            payload = json.dumps(data, default=str)
            if len(payload.encode("utf-8")) > MAX_STATE_DATA_BYTES:
                logger.warning(
                    "Session %s state_data still over %s bytes after trim; skipping DB persist to avoid buffer error",
                    session_id,
                    MAX_STATE_DATA_BYTES,
                )
                return

            db = self._get_db()
            
            # Check if session exists by session_id
            db_session = db.query(Session).filter(Session.session_id == session_id).first()
            
            # If not found by session_id, check by thread_id to avoid duplicates
            # This handles cases where the same conversation might be stored with different keys
            if not db_session and data.get("thread_id"):
                thread_id = data.get("thread_id")
                db_session = db.query(Session).filter(Session.thread_id == thread_id).first()
                
                # If found by thread_id, we should update this existing session
                # and potentially update its session_id to the current one being used
                if db_session:
                    logger.info(f"Found existing session by thread_id {thread_id}, updating with new session_id {session_id}")
                    # Update the session_id to the current key being used
                    db_session.session_id = session_id
            
            # Determine session type from data
            session_type = SessionType.CHAT
            if data.get("conversation_type") == "fnol":
                session_type = SessionType.FNOL
            elif data.get("conversation_type") == "inquiry":
                session_type = SessionType.INQUIRY
            
            # Determine status (active vs ended/completed for transcripts and Salesforce)
            status = SessionStatus.ACTIVE
            if data.get("session_status") == "ended":
                status = SessionStatus.COMPLETED
            elif data.get("fnol_state") == "COMPLETE" or data.get("conversation_state") == "completed":
                status = SessionStatus.COMPLETED
            
            # Get user info if user_id is present and user name/email not in data
            user_id = data.get("user_id")
            user_name = data.get("user_name")
            user_email = data.get("user_email")
            
            if user_id and (not user_name or not user_email):
                try:
                    user = db.query(User).filter(User.user_id == user_id).first()
                    if user:
                        if not user_name:
                            user_name = user.name
                        if not user_email:
                            user_email = user.email
                except Exception as e:
                    logger.warning(f"Could not fetch user info for {user_id}: {e}")
            
            if db_session:
                # Update existing session
                db_session.updated_at = datetime.utcnow()
                db_session.last_activity_at = datetime.utcnow()
                db_session.session_type = session_type
                db_session.status = status
                db_session.state_data = data
                
                # Update metadata if present
                if "user_id" in data:
                    db_session.user_id = data["user_id"]
                if user_name:
                    db_session.user_name = user_name
                if user_email:
                    db_session.user_email = user_email
                if "thread_id" in data:
                    db_session.thread_id = data["thread_id"]
                if "claim_draft_id" in data:
                    db_session.claim_draft_id = data["claim_draft_id"]
                if "claim_number" in data:
                    db_session.claim_number = data["claim_number"]
                
                if status == SessionStatus.COMPLETED:
                    db_session.completed_at = datetime.utcnow()
            else:
                # Create new session
                db_session = Session(
                    session_id=session_id,
                    user_id=user_id,
                    user_name=user_name,
                    user_email=user_email,
                    session_type=session_type,
                    status=status,
                    thread_id=data.get("thread_id"),
                    claim_draft_id=data.get("claim_draft_id"),
                    claim_number=data.get("claim_number"),
                    state_data=data,
                    created_at=datetime.utcnow(),
                    last_activity_at=datetime.utcnow(),
                )
                db.add(db_session)
            
            db.commit()
            logger.debug(f"Persisted session {session_id} to database")
        except Exception as e:
            logger.error(f"Failed to persist session {session_id} to database: {e}")
            # Don't fail the request if DB persistence fails
            db.rollback()
        finally:
            db.close()

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        # Try cache first
        data = self._cache.get(session_id)
        if data:
            return data
        
        # Fall back to database
        try:
            from app.db.models import Session
            db = self._get_db()
            db_session = db.query(Session).filter(Session.session_id == session_id).first()
            db.close()
            
            if db_session:
                # Use to_dict() which merges state_data with session metadata
                data = db_session.to_dict()
                # Cache the state_data part for consistency
                self._cache.set(session_id, db_session.state_data)
                return data
        except Exception as e:
            logger.error(f"Failed to get session {session_id} from database: {e}")
        
        return None

    def set(self, session_id: str, data: Dict[str, Any], ttl_hours: int = 24) -> None:
        # Update cache
        self._cache.set(session_id, data, ttl_hours)
        # Persist to database
        self._persist_to_db(session_id, data)

    def delete(self, session_id: str) -> bool:
        # Delete from cache
        cache_deleted = self._cache.delete(session_id)
        
        # Mark as abandoned in database (don't actually delete for audit purposes)
        try:
            from app.db.models import Session, SessionStatus
            db = self._get_db()
            db_session = db.query(Session).filter(Session.session_id == session_id).first()
            if db_session:
                db_session.status = SessionStatus.ABANDONED
                db_session.updated_at = datetime.utcnow()
                db.commit()
            db.close()
        except Exception as e:
            logger.error(f"Failed to delete session {session_id} from database: {e}")
            db.rollback()
            db.close()
        
        return cache_deleted

    def exists(self, session_id: str) -> bool:
        # Check cache first
        if self._cache.exists(session_id):
            return True
        
        # Check database
        try:
            from app.db.models import Session
            db = self._get_db()
            exists = db.query(Session).filter(Session.session_id == session_id).first() is not None
            db.close()
            return exists
        except Exception as e:
            logger.error(f"Failed to check session existence in database: {e}")
            db.close()
            return False

    def count(self) -> int:
        """Get the number of active sessions from database."""
        try:
            from app.db.models import Session, SessionStatus
            db = self._get_db()
            count = db.query(Session).filter(Session.status == SessionStatus.ACTIVE).count()
            db.close()
            return count
        except Exception as e:
            logger.error(f"Failed to count sessions from database: {e}")
            db.close()
            return 0

    def list_all(self, limit: int = 100, include_completed: bool = False) -> List[Dict[str, Any]]:
        """List all sessions from database (for admin use)."""
        try:
            from app.db.models import Session, SessionStatus, User
            db = self._get_db()
            
            query = db.query(Session).join(User, Session.user_id == User.user_id, isouter=True)
            
            if not include_completed:
                query = query.filter(Session.status == SessionStatus.ACTIVE)
            
            sessions = query.order_by(Session.last_activity_at.desc()).limit(limit).all()
            
            result = []
            for session in sessions:
                session_dict = session.to_dict()
                # Add user name from relationship if not already present
                if session.user and not session_dict.get("user_name"):
                    session_dict["user_name"] = session.user.name
                if session.user and not session_dict.get("user_email"):
                    session_dict["user_email"] = session.user.email
                result.append(session_dict)
            
            db.close()
            return result
        except Exception as e:
            logger.error(f"Failed to list sessions from database: {e}")
            db.close()
            return []


# Singleton session store instance
_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """Get the session store instance (creates if needed)."""
    global _session_store

    if _session_store is not None:
        return _session_store

    # Use DatabaseSessionStore for persistent storage with in-memory cache
    try:
        _session_store = DatabaseSessionStore()
        logger.info("Using database-backed session store with in-memory cache")
    except Exception as e:
        logger.warning(f"Failed to initialize database session store, using in-memory only: {e}")
        _session_store = InMemorySessionStore()

    return _session_store
