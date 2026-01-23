"""
Case and CaseAudit database models (Pega-like case management)
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship

from app.db.base import Base


class CaseStatus(str, PyEnum):
    AI_HANDLING = "ai_handling"
    ESCALATED = "escalated"
    AGENT_HANDLING = "agent_handling"
    RESOLVED = "resolved"


class ActorType(str, PyEnum):
    AI = "ai"
    USER = "user"
    CELEST = "celest"
    ADMIN = "admin"


class Case(Base):
    """Case management for claims (Pega-like workflow)."""

    __tablename__ = "cases"

    case_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.claim_id"), nullable=False)
    chat_thread_id = Column(String(100), nullable=False, index=True)
    status = Column(Enum(CaseStatus), default=CaseStatus.AI_HANDLING, nullable=False)
    stage = Column(String(100), default="intake")  # e.g., intake, review, decision
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    priority = Column(Integer, default=5)  # 1=highest, 10=lowest
    sla_due_at = Column(DateTime, nullable=True)

    # Case locking - prevents multiple agents from working on the same case
    locked_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    locked_at = Column(DateTime, nullable=True)

    # Case packet: summary, extracted_fields, confidence, escalation_reason
    case_packet = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    claim = relationship("Claim", back_populates="case")
    assigned_user = relationship("User", foreign_keys=[assigned_to])
    locked_user = relationship("User", foreign_keys=[locked_by])
    audit_events = relationship("CaseAudit", back_populates="case", cascade="all, delete-orphan")

    # Lock timeout in minutes (locks expire after this time)
    LOCK_TIMEOUT_MINUTES = 15

    def is_locked(self) -> bool:
        """Check if case is currently locked by another user."""
        if not self.locked_by or not self.locked_at:
            return False
        # Check if lock has expired
        from datetime import timedelta
        lock_expiry = self.locked_at + timedelta(minutes=self.LOCK_TIMEOUT_MINUTES)
        return datetime.utcnow() < lock_expiry

    def can_be_locked_by(self, user_id: str) -> bool:
        """Check if user can acquire lock on this case."""
        if not self.is_locked():
            return True
        # User already holds the lock
        return str(self.locked_by) == str(user_id)

    def acquire_lock(self, user_id: str) -> bool:
        """Attempt to acquire lock. Returns True if successful."""
        if not self.can_be_locked_by(user_id):
            return False
        self.locked_by = user_id
        self.locked_at = datetime.utcnow()
        return True

    def release_lock(self, user_id: str) -> bool:
        """Release lock if held by user. Returns True if released."""
        if str(self.locked_by) == str(user_id):
            self.locked_by = None
            self.locked_at = None
            return True
        return False
    
    def __repr__(self) -> str:
        return f"<Case {self.case_id} ({self.status.value})>"


class CaseAudit(Base):
    """Audit trail for case actions."""
    
    __tablename__ = "case_audits"
    
    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.case_id"), nullable=False)
    event_type = Column(String(100), nullable=False)  # e.g., "escalated", "approved", "takeover"
    actor_id = Column(UUID(as_uuid=True), nullable=True)  # Null for AI actions
    actor_type = Column(Enum(ActorType), nullable=False)
    details = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    case = relationship("Case", back_populates="audit_events")
    
    def __repr__(self) -> str:
        return f"<CaseAudit {self.event_type} at {self.timestamp}>"
