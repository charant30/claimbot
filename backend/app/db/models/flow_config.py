"""
Flow configuration database models for admin-configurable document and intent flows.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSON

from app.db.base import Base


class DocumentFlowConfig(Base):
    """Configurable document flow sequences per product line and incident type."""

    __tablename__ = "document_flow_configs"

    config_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_line = Column(String(50), nullable=False, index=True)  # auto, home, medical
    incident_type = Column(String(50), nullable=True, index=True)  # collision, theft, fire, etc.

    # Ordered list of required document types
    document_sequence = Column(JSON, nullable=False, default=list)
    # e.g., ["police_report", "incident_photos", "repair_estimate", "invoice"]

    # Conditional rules for when documents are required
    conditional_rules = Column(JSON, nullable=True, default=dict)
    # e.g., {"incident_photos": {"required_if": "police_report.location_confirmed == false"}}

    # Required fields per document type
    field_requirements = Column(JSON, nullable=True, default=dict)
    # e.g., {"police_report": ["police_report_number", "incident_date"]}

    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Higher priority config takes precedence

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    def __repr__(self) -> str:
        return f"<DocumentFlowConfig {self.product_line}/{self.incident_type}>"

    def to_dict(self) -> dict:
        return {
            "config_id": str(self.config_id),
            "product_line": self.product_line,
            "incident_type": self.incident_type,
            "document_sequence": self.document_sequence,
            "conditional_rules": self.conditional_rules,
            "field_requirements": self.field_requirements,
            "is_active": self.is_active,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class IntentConfig(Base):
    """Configurable intent definitions for the chatbot."""

    __tablename__ = "intent_configs"

    intent_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)  # e.g., "file_claim"
    display_name = Column(String(200), nullable=False)  # e.g., "File a New Claim"
    description = Column(Text, nullable=True)

    # Product lines this intent applies to (null = all)
    applicable_products = Column(JSON, nullable=True)  # e.g., ["auto", "home"]

    # Keywords/phrases that trigger this intent
    trigger_phrases = Column(JSON, nullable=True, default=list)

    # Required fields for this intent
    required_fields = Column(JSON, nullable=True, default=list)

    # Flow configuration - what happens when this intent is triggered
    flow_config = Column(JSON, nullable=True, default=dict)
    # e.g., {"next_step": "collect_info", "escalation_rules": {...}}

    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    icon = Column(String(50), nullable=True)  # emoji or icon name

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<IntentConfig {self.name}>"

    def to_dict(self) -> dict:
        return {
            "intent_id": str(self.intent_id),
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "applicable_products": self.applicable_products,
            "trigger_phrases": self.trigger_phrases,
            "required_fields": self.required_fields,
            "flow_config": self.flow_config,
            "is_active": self.is_active,
            "priority": self.priority,
            "icon": self.icon,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class FlowRule(Base):
    """Configurable flow routing rules."""

    __tablename__ = "flow_rules"

    rule_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # Conditions for when this rule applies
    conditions = Column(JSON, nullable=False, default=dict)
    # e.g., {"intent": "file_claim", "product_line": "auto", "claim_amount_gt": 5000}

    # Action to take when conditions are met
    action = Column(JSON, nullable=False, default=dict)
    # e.g., {"escalate": true, "reason": "High-value claim"}

    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)  # Higher priority rules are evaluated first

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<FlowRule {self.name}>"

    def to_dict(self) -> dict:
        return {
            "rule_id": str(self.rule_id),
            "name": self.name,
            "description": self.description,
            "conditions": self.conditions,
            "action": self.action,
            "is_active": self.is_active,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
