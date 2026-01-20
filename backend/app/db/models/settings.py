"""
SystemSettings database model for admin configuration
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSON

from app.db.base import Base


class SystemSettings(Base):
    """System-wide settings configurable by admin."""
    
    __tablename__ = "system_settings"
    
    setting_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=False)
    description = Column(String(500), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(UUID(as_uuid=True), nullable=True)
    
    def __repr__(self) -> str:
        return f"<SystemSettings {self.key}>"


# Default settings keys:
# - llm_provider: "bedrock" | "ollama"
# - bedrock_model: model ID
# - ollama_model: model name
# - ollama_endpoint: URL
# - confidence_threshold: float
# - auto_approval_limit: float
