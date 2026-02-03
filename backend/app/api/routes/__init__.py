"""
API routes package
"""
from app.api.routes import auth, policies, claims, documents, chat, handoff, admin, websocket

__all__ = [
    "auth",
    "policies",
    "claims",
    "documents",
    "chat",
    "handoff",
    "admin",
    "websocket",
]
