"""
Security middleware for ClaimBot API.
Implements rate limiting, request validation, and security headers.
"""

import time
import hashlib
from collections import defaultdict
from typing import Callable
from fastapi import Request, Response, HTTPException
from fastapi.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware to prevent abuse.
    Uses a sliding window algorithm.
    """
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_size = 60  # seconds
        self.request_counts: dict[str, list[float]] = defaultdict(list)
    
    def _get_client_id(self, request: Request) -> str:
        """Generate a unique client identifier."""
        # Use X-Forwarded-For if behind a proxy, else use client host
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"
        
        # Include user agent for better fingerprinting
        user_agent = request.headers.get("User-Agent", "")
        fingerprint = f"{client_ip}:{user_agent}"
        return hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_id = self._get_client_id(request)
        current_time = time.time()
        
        # Clean old entries
        window_start = current_time - self.window_size
        self.request_counts[client_id] = [
            t for t in self.request_counts[client_id] if t > window_start
        ]
        
        # Check rate limit
        if len(self.request_counts[client_id]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for client {client_id}")
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later."
            )
        
        # Record this request
        self.request_counts[client_id].append(current_time)
        
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = self.requests_per_minute - len(self.request_counts[client_id])
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(window_start + self.window_size))
        
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.
    """
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Content Security Policy (relaxed for development)
        if not settings.DEBUG:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data:; "
                "connect-src 'self'"
            )
        
        return response


class RequestValidationMiddleware(BaseHTTPMiddleware):
    """
    Validate incoming requests for security issues.
    """
    
    MAX_BODY_SIZE = 10 * 1024 * 1024  # 10 MB
    
    BLOCKED_PATHS = [
        "/.env",
        "/.git",
        "/wp-admin",
        "/phpmyadmin",
        "/.aws",
    ]
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Block suspicious paths
        path = request.url.path.lower()
        for blocked in self.BLOCKED_PATHS:
            if path.startswith(blocked):
                logger.warning(f"Blocked suspicious path: {path}")
                raise HTTPException(status_code=404, detail="Not found")
        
        # Check content length
        content_length = request.headers.get("Content-Length")
        if content_length and int(content_length) > self.MAX_BODY_SIZE:
            raise HTTPException(
                status_code=413,
                detail="Request body too large"
            )
        
        return await call_next(request)


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log all API requests for audit purposes.
    """
    
    SENSITIVE_PATHS = ["/auth/", "/admin/"]
    
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log based on path sensitivity
        path = request.url.path
        is_sensitive = any(s in path for s in self.SENSITIVE_PATHS)
        
        log_data = {
            "method": request.method,
            "path": path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "client_ip": request.client.host if request.client else "unknown",
        }
        
        if is_sensitive or response.status_code >= 400:
            logger.info(f"API Request: {log_data}")
        
        return response
