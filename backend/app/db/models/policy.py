"""
Policy and PolicyCoverage database models
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import Column, String, Date, DateTime, Enum, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship

from app.db.base import Base


class ProductType(str, PyEnum):
    AUTO = "auto"
    HOME = "home"
    MEDICAL = "medical"


class PolicyStatus(str, PyEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Policy(Base):
    """Insurance policy model."""
    
    __tablename__ = "policies"
    
    policy_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_number = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    product_type = Column(Enum(ProductType), nullable=False)
    effective_date = Column(Date, nullable=False)
    expiration_date = Column(Date, nullable=False)
    status = Column(Enum(PolicyStatus), default=PolicyStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="policies")
    coverages = relationship("PolicyCoverage", back_populates="policy", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="policy")
    
    def __repr__(self) -> str:
        return f"<Policy {self.policy_number} ({self.product_type.value})>"
    
    def is_active(self) -> bool:
        """Check if policy is currently active."""
        today = date.today()
        return (
            self.status == PolicyStatus.ACTIVE
            and self.effective_date <= today <= self.expiration_date
        )


class PolicyCoverage(Base):
    """Coverage details for a policy."""
    
    __tablename__ = "policy_coverages"
    
    coverage_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("policies.policy_id"), nullable=False)
    coverage_type = Column(String(100), nullable=False)  # e.g., "collision", "liability", "hospital"
    limit_amount = Column(Numeric(12, 2), nullable=False)
    deductible = Column(Numeric(12, 2), default=0)
    copay = Column(Numeric(12, 2), default=0)  # Medical only
    coinsurance_pct = Column(Numeric(5, 2), default=0)  # Medical only (e.g., 20.00 for 20%)
    exclusions = Column(JSON, default=list)  # List of exclusion strings
    
    # Relationships
    policy = relationship("Policy", back_populates="coverages")
    
    def __repr__(self) -> str:
        return f"<Coverage {self.coverage_type} limit={self.limit_amount}>"
