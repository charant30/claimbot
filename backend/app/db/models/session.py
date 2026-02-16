"""
Chat Session database model
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, String, DateTime, Enum, Text, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class SessionType(str, PyEnum):
    FNOL = "fnol"
    CHAT = "chat"
    INQUIRY = "inquiry"


class SessionStatus(str, PyEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class Session(Base):
    """Chat session model for tracking all user conversations."""
    
    __tablename__ = "sessions"
    
    session_id = Column(String(255), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    session_type = Column(Enum(SessionType, values_callable=lambda x: [e.value for e in x]), default=SessionType.CHAT, nullable=False)
    status = Column(Enum(SessionStatus, values_callable=lambda x: [e.value for e in x]), default=SessionStatus.ACTIVE, nullable=False)
    
    # Session metadata
    thread_id = Column(String(255), nullable=True, index=True)
    claim_draft_id = Column(String(255), nullable=True, index=True)
    claim_number = Column(String(100), nullable=True, index=True)
    
    # User context
    user_name = Column(String(255), nullable=True)
    user_email = Column(String(255), nullable=True)
    
    # Session state (JSON)
    state_data = Column(JSON, default={}, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_activity_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    
    def __repr__(self) -> str:
        return f"<Session {self.session_id} ({self.session_type})>"
    
    def to_dict(self):
        """Convert session to dict for API responses."""
        base_dict = {
            "session_id": self.session_id,
            "user_id": str(self.user_id) if self.user_id else None,
            "user_name": self.user_name,
            "user_email": self.user_email,
            "session_type": self.session_type.value if self.session_type else None,
            "status": self.status.value if self.status else None,
            "thread_id": self.thread_id,
            "claim_draft_id": self.claim_draft_id,
            "claim_number": self.claim_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_activity_at": self.last_activity_at.isoformat() if self.last_activity_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
        
        # Merge state_data contents for backwards compatibility with transcript page
        # This allows access to messages, policy_id, etc. at the top level
        if self.state_data:
            state_copy = dict(self.state_data)
            # Don't overwrite base fields with state data
            for key in list(state_copy.keys()):
                if key not in base_dict or base_dict[key] is None:
                    base_dict[key] = state_copy[key]
        
        return base_dict
