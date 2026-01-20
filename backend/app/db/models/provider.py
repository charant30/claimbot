"""
Provider database model (medical network)
"""
import uuid
from enum import Enum as PyEnum

from sqlalchemy import Column, String, Enum
from sqlalchemy.dialects.postgresql import UUID, JSON

from app.db.base import Base


class NetworkStatus(str, PyEnum):
    IN_NETWORK = "in_network"
    OUT_OF_NETWORK = "out_of_network"
    PREFERRED = "preferred"


class Provider(Base):
    """Healthcare provider for medical claims network validation."""
    
    __tablename__ = "providers"
    
    provider_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    npi = Column(String(20), unique=True, nullable=False, index=True)  # National Provider Identifier
    name = Column(String(255), nullable=False)
    specialties = Column(JSON, default=list)  # List of specialty strings
    network_status = Column(Enum(NetworkStatus), default=NetworkStatus.IN_NETWORK, nullable=False)
    
    # Allowed amounts: procedure_code -> allowed_amount mapping
    # e.g., {"99213": 150.00, "99214": 200.00}
    allowed_amounts = Column(JSON, default=dict)
    
    # Address info
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    zip_code = Column(String(20), nullable=True)
    
    def __repr__(self) -> str:
        return f"<Provider {self.name} ({self.network_status.value})>"
    
    def get_allowed_amount(self, procedure_code: str) -> float:
        """Get allowed amount for a procedure code."""
        return self.allowed_amounts.get(procedure_code, 0.0)
