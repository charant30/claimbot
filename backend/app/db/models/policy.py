"""
Policy, PolicyCoverage, PolicyVehicle, and PolicyDriver database models
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import Column, String, Date, DateTime, Enum, ForeignKey, Numeric, Integer, Boolean
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


class DriverRelationship(str, PyEnum):
    """Relationship of driver to policyholder."""
    SELF = "self"
    SPOUSE = "spouse"
    CHILD = "child"
    PARENT = "parent"
    OTHER_RELATIVE = "other_relative"
    OTHER = "other"


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

    # Policyholder information (for identity matching)
    holder_first_name = Column(String(100))
    holder_last_name = Column(String(100))
    holder_phone = Column(String(20))
    holder_email = Column(String(255))
    holder_dob = Column(Date)
    holder_address = Column(String(500))
    holder_zip = Column(String(10))

    # Relationships
    user = relationship("User", back_populates="policies")
    coverages = relationship("PolicyCoverage", back_populates="policy", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="policy")
    vehicles = relationship("PolicyVehicle", back_populates="policy", cascade="all, delete-orphan")
    drivers = relationship("PolicyDriver", back_populates="policy", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Policy {self.policy_number} ({self.product_type.value})>"

    def is_active(self) -> bool:
        """Check if policy is currently active."""
        today = date.today()
        return (
            self.status == PolicyStatus.ACTIVE
            and self.effective_date <= today <= self.expiration_date
        )

    def get_vehicles(self) -> list:
        """Get list of vehicles on this policy."""
        return [v.to_dict() for v in self.vehicles]

    def get_drivers(self) -> list:
        """Get list of drivers on this policy."""
        return [d.to_dict() for d in self.drivers]


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

    # For auto: daily limits (rental reimbursement)
    daily_limit = Column(Numeric(12, 2), nullable=True)
    max_days = Column(Integer, nullable=True)

    # Relationships
    policy = relationship("Policy", back_populates="coverages")

    def __repr__(self) -> str:
        return f"<Coverage {self.coverage_type} limit={self.limit_amount}>"


class PolicyVehicle(Base):
    """Vehicle information for auto policies."""

    __tablename__ = "policy_vehicles"

    vehicle_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("policies.policy_id"), nullable=False)

    # Vehicle identification
    vin = Column(String(17), nullable=False)
    year = Column(Integer, nullable=False)
    make = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    trim = Column(String(100))
    body_type = Column(String(50))  # sedan, suv, truck, etc.
    color = Column(String(50))

    # Registration
    license_plate = Column(String(20))
    license_state = Column(String(10))

    # Vehicle details
    ownership_status = Column(String(20))  # owned, financed, leased
    lienholder_name = Column(String(200))
    lienholder_address = Column(String(500))

    # Garaging location
    garaging_address = Column(String(500))
    garaging_zip = Column(String(10))

    # Usage
    annual_mileage = Column(Integer)
    primary_use = Column(String(50))  # commute, business, pleasure

    # Status
    is_active = Column(Boolean, default=True)

    # Relationships
    policy = relationship("Policy", back_populates="vehicles")

    def __repr__(self) -> str:
        return f"<PolicyVehicle {self.year} {self.make} {self.model}>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "vehicleId": str(self.vehicle_id),
            "vin": self.vin,
            "year": self.year,
            "make": self.make,
            "model": self.model,
            "trim": self.trim,
            "color": self.color,
            "licensePlate": self.license_plate,
            "licenseState": self.license_state,
            "displayName": f"{self.year} {self.make} {self.model}",
        }


class PolicyDriver(Base):
    """Driver information for auto policies."""

    __tablename__ = "policy_drivers"

    driver_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("policies.policy_id"), nullable=False)

    # Driver identification
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(String(10))

    # License information
    license_number = Column(String(50), nullable=False)
    license_state = Column(String(10), nullable=False)
    license_status = Column(String(20), default="valid")  # valid, suspended, revoked
    license_expiration = Column(Date)

    # Relationship to policyholder
    driver_relationship = Column(Enum(DriverRelationship, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    is_primary = Column(Boolean, default=False)  # Primary driver on policy

    # Driving record (simplified)
    years_licensed = Column(Integer)
    accidents_3yr = Column(Integer, default=0)
    violations_3yr = Column(Integer, default=0)

    # Status
    is_active = Column(Boolean, default=True)
    is_excluded = Column(Boolean, default=False)  # Excluded driver

    # Relationships
    policy = relationship("Policy", back_populates="drivers")

    def __repr__(self) -> str:
        return f"<PolicyDriver {self.first_name} {self.last_name}>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "driverId": str(self.driver_id),
            "firstName": self.first_name,
            "lastName": self.last_name,
            "fullName": f"{self.first_name} {self.last_name}",
            "dateOfBirth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "licenseNumber": self.license_number,
            "licenseState": self.license_state,
            "relationship": self.driver_relationship.value if self.driver_relationship else None,
            "isPrimary": self.is_primary,
        }
