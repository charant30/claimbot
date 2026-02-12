"""
Database models package
"""
from app.db.models.user import User, AuthLevel, UserRole
from app.db.models.policy import (
    Policy, PolicyCoverage, PolicyVehicle, PolicyDriver,
    ProductType, PolicyStatus, DriverRelationship
)
from app.db.models.claim import Claim, ClaimType, ClaimStatus
from app.db.models.case import Case, CaseAudit, CaseStatus, ActorType
from app.db.models.document import Document, DocumentType
from app.db.models.provider import Provider, NetworkStatus
from app.db.models.settings import SystemSettings
from app.db.models.audit import AuditLog
from app.db.models.flow_config import DocumentFlowConfig, IntentConfig, FlowRule

# FNOL (First Notice of Loss) models
from app.db.models.fnol_enums import (
    ClaimDraftStatus, TriageRoute, LossType, CollisionType, WeatherType, TheftType,
    VehicleRole, PartyRole, InjurySeverity, TreatmentLevel, EvidenceType, EvidenceSubtype,
    DamageArea, DamageType, ImpactType, PoliceContactStatus, DrivableStatus,
    PolicyMatchStatus, FNOLState, UseType
)
from app.db.models.claim_draft import (
    ClaimDraft, ClaimDraftVehicle, ClaimDraftParty, ClaimDraftImpact,
    ClaimDraftInjury, ClaimDraftDamage, ClaimDraftEvidence, ClaimDraftAudit
)

__all__ = [
    # User
    "User",
    "AuthLevel",
    "UserRole",
    # Policy
    "Policy",
    "PolicyCoverage",
    "PolicyVehicle",
    "PolicyDriver",
    "ProductType",
    "PolicyStatus",
    "DriverRelationship",
    # Claim
    "Claim",
    "ClaimType",
    "ClaimStatus",
    # Case
    "Case",
    "CaseAudit",
    "CaseStatus",
    "ActorType",
    # Document
    "Document",
    "DocumentType",
    # Provider
    "Provider",
    "NetworkStatus",
    # Settings
    "SystemSettings",
    # Audit
    "AuditLog",
    # Flow Config
    "DocumentFlowConfig",
    "IntentConfig",
    "FlowRule",
    # FNOL Enums
    "ClaimDraftStatus",
    "TriageRoute",
    "LossType",
    "CollisionType",
    "WeatherType",
    "TheftType",
    "VehicleRole",
    "PartyRole",
    "InjurySeverity",
    "TreatmentLevel",
    "EvidenceType",
    "EvidenceSubtype",
    "DamageArea",
    "DamageType",
    "ImpactType",
    "PoliceContactStatus",
    "DrivableStatus",
    "PolicyMatchStatus",
    "FNOLState",
    "UseType",
    # FNOL Models
    "ClaimDraft",
    "ClaimDraftVehicle",
    "ClaimDraftParty",
    "ClaimDraftImpact",
    "ClaimDraftInjury",
    "ClaimDraftDamage",
    "ClaimDraftEvidence",
    "ClaimDraftAudit",
]
