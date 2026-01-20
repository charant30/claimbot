"""
Claim database model
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import Column, String, Date, DateTime, Enum, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship

from app.db.base import Base


class ClaimType(str, PyEnum):
    INCIDENT = "incident"  # Auto/Home
    MEDICAL = "medical"


class ClaimStatus(str, PyEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    DENIED = "denied"
    PAID = "paid"


class Claim(Base):
    """Insurance claim model."""
    
    __tablename__ = "claims"
    
    claim_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("policies.policy_id"), nullable=False)
    claim_number = Column(String(50), unique=True, nullable=False, index=True)
    claim_type = Column(Enum(ClaimType), nullable=False)
    status = Column(Enum(ClaimStatus), default=ClaimStatus.DRAFT, nullable=False)
    incident_date = Column(Date, nullable=False)
    loss_amount = Column(Numeric(12, 2), default=0)
    reserves = Column(Numeric(12, 2), default=0)
    paid_amount = Column(Numeric(12, 2), default=0)
    
    # Timeline: list of {status, timestamp, actor, notes}
    timeline = Column(JSON, default=list)
    
    # Metadata varies by claim type:
    # Incident: {location, description, police_report_number, vehicle_info, ...}
    # Medical: {provider_npi, diagnosis_codes, procedure_codes, service_date, ...}
    metadata = Column(JSON, default=dict)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    policy = relationship("Policy", back_populates="claims")
    documents = relationship("Document", back_populates="claim", cascade="all, delete-orphan")
    case = relationship("Case", back_populates="claim", uselist=False)
    
    def __repr__(self) -> str:
        return f"<Claim {self.claim_number} ({self.status.value})>"
    
    def add_timeline_event(self, status: str, actor: str, notes: str = "") -> None:
        """Add an event to the claim timeline."""
        if self.timeline is None:
            self.timeline = []
        self.timeline.append({
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "actor": actor,
            "notes": notes,
        })
