"""
User database model
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, String, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class AuthLevel(str, PyEnum):
    GUEST = "guest"
    AUTH = "auth"


class UserRole(str, PyEnum):
    CUSTOMER = "customer"
    CELEST = "celest"
    ADMIN = "admin"


class User(Base):
    """User account model."""
    
    __tablename__ = "users"
    
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    auth_level = Column(Enum(AuthLevel), default=AuthLevel.AUTH, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.CUSTOMER, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    policies = relationship("Policy", back_populates="user")
    
    def __repr__(self) -> str:
        return f"<User {self.email}>"
