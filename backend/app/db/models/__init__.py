"""
Database models package
"""
from app.db.models.user import User, AuthLevel, UserRole
from app.db.models.policy import Policy, PolicyCoverage, ProductType, PolicyStatus
from app.db.models.claim import Claim, ClaimType, ClaimStatus
from app.db.models.case import Case, CaseAudit, CaseStatus, ActorType
from app.db.models.document import Document, DocumentType
from app.db.models.provider import Provider, NetworkStatus
from app.db.models.settings import SystemSettings
from app.db.models.audit import AuditLog

__all__ = [
    # User
    "User",
    "AuthLevel",
    "UserRole",
    # Policy
    "Policy",
    "PolicyCoverage",
    "ProductType",
    "PolicyStatus",
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
]
