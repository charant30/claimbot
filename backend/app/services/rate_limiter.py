"""
Rate Limiter Service - Provides rate limiting for API endpoints.

Uses a sliding window counter algorithm with Redis or in-memory storage.
"""
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from abc import ABC, abstractmethod

from fastapi import HTTPException, Request, status
from app.core.config import settings
from app.core.logging import logger


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit rule."""
    requests: int  # Number of requests allowed
    window_seconds: int  # Time window in seconds
    key_prefix: str = ""  # Optional prefix for the key


class RateLimitStore(ABC):
    """Abstract base class for rate limit storage."""

    @abstractmethod
    def increment(self, key: str, window_seconds: int) -> Tuple[int, int]:
        """
        Increment the counter for a key.

        Returns:
            Tuple of (current_count, seconds_until_reset)
        """
        pass

    @abstractmethod
    def get_count(self, key: str) -> int:
        """Get the current count for a key."""
        pass


class InMemoryRateLimitStore(RateLimitStore):
    """In-memory rate limit store for development."""

    def __init__(self):
        self._counters: Dict[str, Dict] = {}

    def _cleanup_expired(self):
        """Remove expired windows."""
        now = datetime.utcnow()
        expired = [
            k for k, v in self._counters.items()
            if v.get("expires_at", now) < now
        ]
        for key in expired:
            del self._counters[key]

    def increment(self, key: str, window_seconds: int) -> Tuple[int, int]:
        self._cleanup_expired()
        now = datetime.utcnow()

        if key not in self._counters:
            expires_at = now + timedelta(seconds=window_seconds)
            self._counters[key] = {
                "count": 1,
                "expires_at": expires_at,
                "window_start": now,
            }
            return (1, window_seconds)

        entry = self._counters[key]
        if entry["expires_at"] < now:
            # Window expired, start new window
            expires_at = now + timedelta(seconds=window_seconds)
            self._counters[key] = {
                "count": 1,
                "expires_at": expires_at,
                "window_start": now,
            }
            return (1, window_seconds)

        entry["count"] += 1
        seconds_until_reset = int((entry["expires_at"] - now).total_seconds())
        return (entry["count"], seconds_until_reset)

    def get_count(self, key: str) -> int:
        self._cleanup_expired()
        entry = self._counters.get(key)
        if entry and entry.get("expires_at", datetime.min) > datetime.utcnow():
            return entry.get("count", 0)
        return 0


class RedisRateLimitStore(RateLimitStore):
    """Redis-backed rate limit store for production."""

    def __init__(self, redis_url: str):
        import redis
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._prefix = "claimbot:ratelimit:"

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def increment(self, key: str, window_seconds: int) -> Tuple[int, int]:
        redis_key = self._key(key)
        pipe = self._redis.pipeline()
        pipe.incr(redis_key)
        pipe.ttl(redis_key)
        results = pipe.execute()

        count = results[0]
        ttl = results[1]

        # Set expiry if this is a new key (ttl = -1 means no expiry set)
        if ttl == -1:
            self._redis.expire(redis_key, window_seconds)
            ttl = window_seconds

        return (count, max(ttl, 0))

    def get_count(self, key: str) -> int:
        redis_key = self._key(key)
        count = self._redis.get(redis_key)
        return int(count) if count else 0


# Default rate limit configurations
DEFAULT_RATE_LIMITS = {
    "fnol_session": RateLimitConfig(
        requests=10,  # 10 new sessions
        window_seconds=60,  # per minute
        key_prefix="fnol_session",
    ),
    "fnol_message": RateLimitConfig(
        requests=60,  # 60 messages
        window_seconds=60,  # per minute
        key_prefix="fnol_message",
    ),
    "fnol_document": RateLimitConfig(
        requests=20,  # 20 uploads
        window_seconds=60,  # per minute
        key_prefix="fnol_document",
    ),
}


class RateLimiter:
    """Rate limiter with configurable limits per endpoint."""

    def __init__(self, store: RateLimitStore):
        self._store = store
        self._configs = DEFAULT_RATE_LIMITS.copy()

    def add_config(self, name: str, config: RateLimitConfig):
        """Add or update a rate limit configuration."""
        self._configs[name] = config

    def check(
        self,
        config_name: str,
        identifier: str,
        raise_on_limit: bool = True,
    ) -> Tuple[bool, int, int]:
        """
        Check if a request is within rate limits.

        Args:
            config_name: Name of the rate limit config to use
            identifier: Unique identifier (IP, user_id, etc.)
            raise_on_limit: Whether to raise HTTPException if limited

        Returns:
            Tuple of (allowed, current_count, seconds_until_reset)
        """
        config = self._configs.get(config_name)
        if not config:
            # No limit configured, allow all
            return (True, 0, 0)

        key = f"{config.key_prefix}:{identifier}"
        count, reset_seconds = self._store.increment(key, config.window_seconds)

        allowed = count <= config.requests

        if not allowed and raise_on_limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {reset_seconds} seconds.",
                headers={
                    "X-RateLimit-Limit": str(config.requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_seconds),
                    "Retry-After": str(reset_seconds),
                },
            )

        return (allowed, count, reset_seconds)

    def get_headers(self, config_name: str, identifier: str) -> Dict[str, str]:
        """Get rate limit headers for a response."""
        config = self._configs.get(config_name)
        if not config:
            return {}

        key = f"{config.key_prefix}:{identifier}"
        count = self._store.get_count(key)
        remaining = max(0, config.requests - count)

        return {
            "X-RateLimit-Limit": str(config.requests),
            "X-RateLimit-Remaining": str(remaining),
        }


# Singleton rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the rate limiter instance (creates if needed)."""
    global _rate_limiter

    if _rate_limiter is not None:
        return _rate_limiter

    # Try Redis first, fall back to in-memory
    if settings.REDIS_URL and settings.APP_ENV != "development":
        try:
            store = RedisRateLimitStore(settings.REDIS_URL)
            store._redis.ping()
            logger.info("Using Redis rate limit store")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis for rate limiting, using in-memory: {e}")
            store = InMemoryRateLimitStore()
    else:
        logger.info("Using in-memory rate limit store (development mode)")
        store = InMemoryRateLimitStore()

    _rate_limiter = RateLimiter(store)
    return _rate_limiter


def get_client_identifier(request: Request, user_id: Optional[str] = None) -> str:
    """
    Get a unique identifier for rate limiting.

    Uses user_id if authenticated, otherwise falls back to IP address.
    """
    if user_id:
        return f"user:{user_id}"

    # Get client IP (handle proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP (client IP)
        return f"ip:{forwarded_for.split(',')[0].strip()}"

    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"
