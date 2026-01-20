"""
Audit database model for system-wide audit logging
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSON

from app.db.base import Base


class AuditLog(Base):
    """System-wide audit log for all operations."""
    
    __tablename__ = "audit_logs"
    
    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(100), nullable=False, index=True)
    
    # Resource being accessed/modified
    resource_type = Column(String(50), nullable=True)  # e.g., "policy", "claim", "user"
    resource_id = Column(String(100), nullable=True)
    
    # Actor
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    actor_type = Column(String(50), nullable=False)  # e.g., "user", "ai", "system"
    actor_role = Column(String(50), nullable=True)
    
    # Details
    action = Column(String(100), nullable=False)  # e.g., "read", "create", "update", "delete"
    details = Column(JSON, default=dict)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self) -> str:
        return f"<AuditLog {self.event_type} at {self.timestamp}>"
