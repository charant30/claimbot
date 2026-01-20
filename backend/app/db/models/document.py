"""
Document database model
"""
import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, String, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import relationship

from app.db.base import Base


class DocumentType(str, PyEnum):
    PHOTO = "photo"
    POLICE_REPORT = "police_report"
    MEDICAL_RECORD = "medical_record"
    EOB = "eob"  # Explanation of Benefits
    INVOICE = "invoice"
    ESTIMATE = "estimate"
    OTHER = "other"


class Document(Base):
    """Document attached to a claim."""
    
    __tablename__ = "documents"
    
    doc_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.claim_id"), nullable=False)
    doc_type = Column(Enum(DocumentType), nullable=False)
    filename = Column(String(255), nullable=False)
    storage_url = Column(String(500), nullable=False)
    content_type = Column(String(100), nullable=True)
    file_size = Column(String(50), nullable=True)
    
    # Extracted entities from OCR/AI processing
    extracted_entities = Column(JSON, default=dict)
    
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    claim = relationship("Claim", back_populates="documents")
    
    def __repr__(self) -> str:
        return f"<Document {self.filename} ({self.doc_type.value})>"
