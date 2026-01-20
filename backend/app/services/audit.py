"""
Enhanced audit service for ClaimBot.
Provides comprehensive audit logging with data classification.
"""

from datetime import datetime
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.db.models import AuditLog
from app.core.data_classification import (
    sanitize_for_logging,
    classify_request_body,
    DataClassification,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class AuditService:
    """Service for creating and querying audit logs."""
    
    # Event type categories
    AUTH_EVENTS = ["user.login", "user.logout", "user.signup", "user.guest_session"]
    CLAIM_EVENTS = ["claim.created", "claim.updated", "claim.submitted", "claim.approved", "claim.denied"]
    CASE_EVENTS = ["case.escalated", "case.takeover", "case.released", "case.resolved"]
    ADMIN_EVENTS = ["settings.changed", "user.role_changed", "flow.updated"]
    SECURITY_EVENTS = ["auth.failed", "access.denied", "rate.limited", "suspicious.activity"]
    
    def __init__(self, db: Session):
        self.db = db
    
    def log(
        self,
        event_type: str,
        actor_type: str,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        details: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """
        Create an audit log entry.
        
        Args:
            event_type: Type of event (e.g., "user.login", "claim.created")
            actor_type: Who performed the action ("user", "admin", "system", "ai")
            actor_id: ID of the actor
            resource_type: Type of resource affected
            resource_id: ID of the resource
            details: Additional event details (will be sanitized)
            ip_address: Client IP address
            user_agent: Client user agent
        """
        # Sanitize details to remove sensitive data
        sanitized_details = sanitize_for_logging(details or {})
        
        # Add metadata
        sanitized_details["_metadata"] = {
            "timestamp": datetime.utcnow().isoformat(),
            "ip_address": ip_address,
            "data_classification": classify_request_body(details or {}).value,
        }
        
        audit_log = AuditLog(
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=sanitized_details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)
        
        # Log to application logs as well for real-time monitoring
        log_msg = f"AUDIT: {event_type} | {actor_type}:{actor_id} | {resource_type}:{resource_id}"
        if event_type in self.SECURITY_EVENTS:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
        
        return audit_log
    
    def log_auth_event(
        self,
        event_type: str,
        user_id: str,
        success: bool,
        ip_address: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> AuditLog:
        """Log an authentication event."""
        return self.log(
            event_type=event_type,
            actor_type="user",
            actor_id=user_id,
            resource_type="session",
            resource_id=f"session_{user_id}",
            details={**(details or {}), "success": success},
            ip_address=ip_address,
        )
    
    def log_claim_event(
        self,
        event_type: str,
        user_id: str,
        claim_id: str,
        details: Optional[dict] = None,
    ) -> AuditLog:
        """Log a claim-related event."""
        return self.log(
            event_type=event_type,
            actor_type="user",
            actor_id=user_id,
            resource_type="claim",
            resource_id=claim_id,
            details=details,
        )
    
    def log_case_event(
        self,
        event_type: str,
        agent_id: str,
        case_id: str,
        details: Optional[dict] = None,
    ) -> AuditLog:
        """Log a case/escalation event."""
        return self.log(
            event_type=event_type,
            actor_type="celest",
            actor_id=agent_id,
            resource_type="case",
            resource_id=case_id,
            details=details,
        )
    
    def log_admin_event(
        self,
        event_type: str,
        admin_id: str,
        resource_type: str,
        resource_id: str,
        details: Optional[dict] = None,
    ) -> AuditLog:
        """Log an admin action."""
        return self.log(
            event_type=event_type,
            actor_type="admin",
            actor_id=admin_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )
    
    def log_security_event(
        self,
        event_type: str,
        actor_id: str,
        ip_address: str,
        details: Optional[dict] = None,
    ) -> AuditLog:
        """Log a security-related event."""
        return self.log(
            event_type=event_type,
            actor_type="system",
            actor_id=actor_id,
            resource_type="security",
            resource_id=f"security_{event_type}",
            details=details,
            ip_address=ip_address,
        )
    
    def get_user_activity(
        self,
        user_id: str,
        limit: int = 50,
    ) -> list[AuditLog]:
        """Get activity history for a user."""
        return (
            self.db.query(AuditLog)
            .filter(AuditLog.actor_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )
    
    def get_resource_history(
        self,
        resource_type: str,
        resource_id: str,
        limit: int = 50,
    ) -> list[AuditLog]:
        """Get audit history for a specific resource."""
        return (
            self.db.query(AuditLog)
            .filter(
                AuditLog.resource_type == resource_type,
                AuditLog.resource_id == resource_id,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )
    
    def get_security_events(
        self,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        """Get recent security events for monitoring."""
        query = self.db.query(AuditLog).filter(
            AuditLog.event_type.in_(self.SECURITY_EVENTS)
        )
        
        if since:
            query = query.filter(AuditLog.created_at >= since)
        
        return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
