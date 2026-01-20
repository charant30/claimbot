"""
Handoff API routes (Celest escalation)
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
import uuid as uuid_lib
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import Case, CaseAudit, CaseStatus, ActorType, Claim, User, UserRole
from app.core import get_current_user_id, require_role, logger, log_audit_event

router = APIRouter()


# Request/Response schemas
class CreateHandoffRequest(BaseModel):
    claim_id: str
    thread_id: str
    reason: str
    case_packet: Dict[str, Any] = {}
    priority: int = 5


class HandoffActionRequest(BaseModel):
    action: str  # "approve", "deny", "request_info"
    notes: str = ""
    metadata: Dict[str, Any] = {}


class CaseResponse(BaseModel):
    case_id: str
    claim_id: str
    thread_id: str
    status: str
    stage: str
    priority: int
    assigned_to: Optional[str]
    case_packet: Dict[str, Any]
    created_at: str
    sla_due_at: Optional[str]


@router.post("/create", response_model=CaseResponse)
async def create_handoff(
    request: CreateHandoffRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Escalate a case to Celest for human review."""
    # Validate claim exists
    claim = db.query(Claim).filter(Claim.claim_id == request.claim_id).first()
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )
    
    # Check if case already exists
    existing = db.query(Case).filter(Case.claim_id == request.claim_id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Case already exists for this claim",
        )
    
    # Create case
    case = Case(
        claim_id=claim.claim_id,
        chat_thread_id=request.thread_id,
        status=CaseStatus.ESCALATED,
        stage="escalated",
        priority=request.priority,
        sla_due_at=datetime.utcnow() + timedelta(hours=24),
        case_packet={
            **request.case_packet,
            "escalation_reason": request.reason,
        },
    )
    
    db.add(case)
    db.commit()
    db.refresh(case)
    
    # Add audit event
    audit = CaseAudit(
        case_id=case.case_id,
        event_type="escalated",
        actor_id=None,
        actor_type=ActorType.AI,
        details={"reason": request.reason},
    )
    db.add(audit)
    db.commit()
    
    log_audit_event(
        "case_escalated",
        "ai",
        "ai",
        {"case_id": str(case.case_id), "reason": request.reason},
    )
    
    return CaseResponse(
        case_id=str(case.case_id),
        claim_id=str(case.claim_id),
        thread_id=case.chat_thread_id,
        status=case.status.value,
        stage=case.stage,
        priority=case.priority,
        assigned_to=str(case.assigned_to) if case.assigned_to else None,
        case_packet=case.case_packet,
        created_at=case.created_at.isoformat(),
        sla_due_at=case.sla_due_at.isoformat() if case.sla_due_at else None,
    )


@router.get("/queue", response_model=List[CaseResponse])
async def get_escalation_queue(
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Get all escalated cases (Celest queue)."""
    cases = (
        db.query(Case)
        .filter(Case.status.in_([CaseStatus.ESCALATED, CaseStatus.AGENT_HANDLING]))
        .order_by(Case.priority.asc(), Case.created_at.asc())
        .all()
    )
    
    return [
        CaseResponse(
            case_id=str(c.case_id),
            claim_id=str(c.claim_id),
            thread_id=c.chat_thread_id,
            status=c.status.value,
            stage=c.stage,
            priority=c.priority,
            assigned_to=str(c.assigned_to) if c.assigned_to else None,
            case_packet=c.case_packet or {},
            created_at=c.created_at.isoformat(),
            sla_due_at=c.sla_due_at.isoformat() if c.sla_due_at else None,
        )
        for c in cases
    ]


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: UUID,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Get case details."""
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )
    
    return CaseResponse(
        case_id=str(case.case_id),
        claim_id=str(case.claim_id),
        thread_id=case.chat_thread_id,
        status=case.status.value,
        stage=case.stage,
        priority=case.priority,
        assigned_to=str(case.assigned_to) if case.assigned_to else None,
        case_packet=case.case_packet or {},
        created_at=case.created_at.isoformat(),
        sla_due_at=case.sla_due_at.isoformat() if case.sla_due_at else None,
    )


@router.post("/{case_id}/approve")
async def approve_case(
    case_id: UUID,
    request: HandoffActionRequest,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Approve a case action."""
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )
    
    user_id = payload.get("sub")
    
    case.status = CaseStatus.RESOLVED
    case.stage = "approved"
    case.resolved_at = datetime.utcnow()
    
    # Update claim status
    claim = case.claim
    from app.db.models import ClaimStatus
    claim.status = ClaimStatus.APPROVED
    claim.add_timeline_event("approved", user_id, request.notes)
    
    # Add audit
    audit = CaseAudit(
        case_id=case.case_id,
        event_type="approved",
        actor_id=user_id,
        actor_type=ActorType.CELEST,
        details={"notes": request.notes},
    )
    db.add(audit)
    db.commit()
    
    log_audit_event("case_approved", user_id, "celest", {"case_id": str(case_id)})
    
    return {"message": "Case approved", "case_id": str(case_id)}


@router.post("/{case_id}/request-info")
async def request_more_info(
    case_id: UUID,
    request: HandoffActionRequest,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Request more information from the customer."""
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )
    
    user_id = payload.get("sub")
    
    case.stage = "pending_info"
    case.case_packet["info_requested"] = request.notes
    
    # Add audit
    audit = CaseAudit(
        case_id=case.case_id,
        event_type="info_requested",
        actor_id=user_id,
        actor_type=ActorType.CELEST,
        details={"notes": request.notes},
    )
    db.add(audit)
    db.commit()
    
    log_audit_event("info_requested", user_id, "celest", {"case_id": str(case_id)})
    
    return {"message": "Information requested", "case_id": str(case_id)}


@router.post("/{case_id}/takeover")
async def takeover_chat(
    case_id: UUID,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Take over live chat from AI."""
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )
    
    user_id = payload.get("sub")
    
    case.status = CaseStatus.AGENT_HANDLING
    case.assigned_to = user_id
    
    # Add audit
    audit = CaseAudit(
        case_id=case.case_id,
        event_type="takeover",
        actor_id=user_id,
        actor_type=ActorType.CELEST,
        details={},
    )
    db.add(audit)
    db.commit()
    
    log_audit_event("chat_takeover", user_id, "celest", {"case_id": str(case_id)})
    
    return {
        "message": "Chat takeover successful",
        "case_id": str(case_id),
        "thread_id": case.chat_thread_id,
    }
