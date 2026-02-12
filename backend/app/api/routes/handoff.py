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
from app.db.models import Case, CaseAudit, CaseStatus, ActorType, Claim, Document, Policy
from app.core import get_current_user_id, require_role, logger, log_audit_event
from app.services.session_store import get_session_store
from app.services.document_integration import get_documents_for_claim

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


class DenyCaseRequest(BaseModel):
    reason: str


class RequestInfoRequest(BaseModel):
    questions: List[str] = []
    notes: str = ""


class AgentMessageRequest(BaseModel):
    message: str


class CaseMessageResponse(BaseModel):
    role: str
    content: str
    created_at: str
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
    # Lock information
    locked_by: Optional[str] = None
    locked_at: Optional[str] = None
    is_locked: bool = False


def case_to_response(case: Case) -> CaseResponse:
    """Convert Case model to CaseResponse."""
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
        locked_by=str(case.locked_by) if case.locked_by else None,
        locked_at=case.locked_at.isoformat() if case.locked_at else None,
        is_locked=case.is_locked(),
    )


def _get_case_or_404(db: Session, case_id: UUID) -> Case:
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )
    return case


def _ensure_lock(case: Case, user_id: str) -> None:
    if case.is_locked() and not case.can_be_locked_by(user_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Case is locked by another agent",
        )


def _approve_case(case: Case, user_id: str, notes: str, db: Session) -> None:
    case.status = CaseStatus.RESOLVED
    case.stage = "approved"
    case.resolved_at = datetime.utcnow()
    case.locked_by = None
    case.locked_at = None

    claim = case.claim
    from app.db.models import ClaimStatus
    claim.status = ClaimStatus.APPROVED
    claim.add_timeline_event("approved", user_id, notes)

    audit = CaseAudit(
        case_id=case.case_id,
        event_type="approved",
        actor_id=user_id,
        actor_type=ActorType.CELEST,
        details={"notes": notes},
    )
    db.add(audit)
    db.commit()

    log_audit_event("case_approved", user_id, "celest", {"case_id": str(case.case_id)})


def _deny_case(case: Case, user_id: str, reason: str, db: Session) -> None:
    case.status = CaseStatus.RESOLVED
    case.stage = "denied"
    case.resolved_at = datetime.utcnow()
    case.locked_by = None
    case.locked_at = None

    claim = case.claim
    from app.db.models import ClaimStatus
    claim.status = ClaimStatus.DENIED
    claim.add_timeline_event("denied", user_id, reason)

    audit = CaseAudit(
        case_id=case.case_id,
        event_type="denied",
        actor_id=user_id,
        actor_type=ActorType.CELEST,
        details={"reason": reason},
    )
    db.add(audit)
    db.commit()

    log_audit_event("case_denied", user_id, "celest", {"case_id": str(case.case_id)})


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

    return case_to_response(case)


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

    return [case_to_response(c) for c in cases]


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: UUID,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Get case details."""
    case = _get_case_or_404(db, case_id)

    return case_to_response(case)


@router.get("/case/{case_id}", response_model=CaseResponse)
async def get_case_alias(
    case_id: UUID,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Get case details (alias for frontend)."""
    case = _get_case_or_404(db, case_id)
    return case_to_response(case)


@router.post("/{case_id}/lock")
async def lock_case(
    case_id: UUID,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Acquire a lock on a case to prevent other agents from working on it."""
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    user_id = payload.get("sub")

    if not case.acquire_lock(user_id):
        locked_by_name = "another agent"
        if case.locked_user:
            locked_by_name = case.locked_user.name
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Case is currently locked by {locked_by_name}",
        )

    db.commit()
    logger.info(f"Case {case_id} locked by {user_id}")

    return {"message": "Case locked successfully", "case_id": str(case_id)}


@router.post("/{case_id}/unlock")
async def unlock_case(
    case_id: UUID,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Release a lock on a case."""
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    user_id = payload.get("sub")

    if not case.release_lock(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not hold the lock on this case",
        )

    db.commit()
    logger.info(f"Case {case_id} unlocked by {user_id}")

    return {"message": "Case unlocked successfully", "case_id": str(case_id)}


@router.post("/{case_id}/approve")
async def approve_case(
    case_id: UUID,
    request: HandoffActionRequest,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Approve a case action."""
    case = _get_case_or_404(db, case_id)

    user_id = payload.get("sub")

    # Check lock - user must hold lock or case must be unlocked
    _ensure_lock(case, user_id)
    _approve_case(case, user_id, request.notes, db)

    return {"message": "Case approved", "case_id": str(case_id)}


@router.post("/case/{case_id}/approve")
async def approve_case_alias(
    case_id: UUID,
    request: HandoffActionRequest,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Approve a case action (alias for frontend)."""
    case = _get_case_or_404(db, case_id)
    user_id = payload.get("sub")
    _ensure_lock(case, user_id)
    _approve_case(case, user_id, request.notes, db)
    return {"message": "Case approved", "case_id": str(case_id)}


@router.post("/{case_id}/deny")
async def deny_case(
    case_id: UUID,
    request: DenyCaseRequest,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Deny a case action."""
    case = _get_case_or_404(db, case_id)
    user_id = payload.get("sub")
    _ensure_lock(case, user_id)
    _deny_case(case, user_id, request.reason, db)
    return {"message": "Case denied", "case_id": str(case_id)}


@router.post("/case/{case_id}/deny")
async def deny_case_alias(
    case_id: UUID,
    request: DenyCaseRequest,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Deny a case action (alias for frontend)."""
    case = _get_case_or_404(db, case_id)
    user_id = payload.get("sub")
    _ensure_lock(case, user_id)
    _deny_case(case, user_id, request.reason, db)
    return {"message": "Case denied", "case_id": str(case_id)}


@router.post("/{case_id}/request-info")
async def request_more_info(
    case_id: UUID,
    request: RequestInfoRequest,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Request more information from the customer."""
    case = _get_case_or_404(db, case_id)

    user_id = payload.get("sub")

    # Check lock
    _ensure_lock(case, user_id)

    case.stage = "pending_info"
    case.case_packet["info_requested"] = request.questions or []
    case.case_packet["info_notes"] = request.notes
    
    # Add audit
    audit = CaseAudit(
        case_id=case.case_id,
        event_type="info_requested",
        actor_id=user_id,
        actor_type=ActorType.CELEST,
        details={"notes": request.notes, "questions": request.questions},
    )
    db.add(audit)
    db.commit()
    
    log_audit_event("info_requested", user_id, "celest", {"case_id": str(case_id)})
    
    return {"message": "Information requested", "case_id": str(case_id)}


@router.post("/case/{case_id}/request-info")
async def request_more_info_alias(
    case_id: UUID,
    request: RequestInfoRequest,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Request more information from the customer (alias for frontend)."""
    case = _get_case_or_404(db, case_id)
    user_id = payload.get("sub")
    _ensure_lock(case, user_id)
    case.stage = "pending_info"
    case.case_packet["info_requested"] = request.questions or []
    case.case_packet["info_notes"] = request.notes

    audit = CaseAudit(
        case_id=case.case_id,
        event_type="info_requested",
        actor_id=user_id,
        actor_type=ActorType.CELEST,
        details={"notes": request.notes, "questions": request.questions},
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
    case = _get_case_or_404(db, case_id)

    user_id = payload.get("sub")

    # Check lock - if locked by another agent, reject takeover
    _ensure_lock(case, user_id)

    # Acquire lock when taking over
    case.acquire_lock(user_id)
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


@router.post("/case/{case_id}/takeover")
async def takeover_chat_alias(
    case_id: UUID,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Take over live chat from AI (alias for frontend)."""
    case = _get_case_or_404(db, case_id)
    user_id = payload.get("sub")
    _ensure_lock(case, user_id)
    case.acquire_lock(user_id)
    case.status = CaseStatus.AGENT_HANDLING
    case.assigned_to = user_id

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


@router.get("/case/{case_id}/messages", response_model=List[CaseMessageResponse])
async def get_case_messages(
    case_id: UUID,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Get case messages for agent view."""
    case = _get_case_or_404(db, case_id)
    session_store = get_session_store()
    session = session_store.get(case.chat_thread_id)
    if not session:
        return []
    return [
        CaseMessageResponse(
            role=msg.get("role", "assistant"),
            content=msg.get("content", ""),
            created_at=msg.get("created_at", ""),
            metadata=msg.get("metadata", {}),
        )
        for msg in session.get("messages", [])
    ]


@router.post("/case/{case_id}/message", response_model=CaseMessageResponse)
async def send_case_message(
    case_id: UUID,
    request: AgentMessageRequest,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Send an agent message during takeover."""
    case = _get_case_or_404(db, case_id)
    user_id = payload.get("sub")
    _ensure_lock(case, user_id)

    session_store = get_session_store()
    session = session_store.get(case.chat_thread_id) or {
        "thread_id": case.chat_thread_id,
        "messages": [],
    }

    message = {
        "message_id": str(uuid_lib.uuid4()),
        "role": "agent",
        "content": request.message,
        "metadata": {"actor_id": user_id},
        "created_at": datetime.utcnow().isoformat(),
    }
    session["messages"].append(message)
    session_store.set(case.chat_thread_id, session, ttl_hours=24)

    audit = CaseAudit(
        case_id=case.case_id,
        event_type="agent_message",
        actor_id=user_id,
        actor_type=ActorType.CELEST,
        details={"message_id": message["message_id"]},
    )
    db.add(audit)
    db.commit()

    return CaseMessageResponse(
        role=message["role"],
        content=message["content"],
        created_at=message["created_at"],
        metadata=message["metadata"],
    )


@router.post("/case/{case_id}/release")
async def release_case(
    case_id: UUID,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Release case back to AI handling."""
    case = _get_case_or_404(db, case_id)
    user_id = payload.get("sub")
    _ensure_lock(case, user_id)

    case.status = CaseStatus.AI_HANDLING
    case.stage = "ai_handling"
    case.assigned_to = None
    case.release_lock(user_id)

    audit = CaseAudit(
        case_id=case.case_id,
        event_type="released",
        actor_id=user_id,
        actor_type=ActorType.CELEST,
        details={},
    )
    db.add(audit)
    db.commit()

    log_audit_event("case_released", user_id, "celest", {"case_id": str(case_id)})

    return {"message": "Case released", "case_id": str(case_id)}


# =============================================================================
# Document Viewer Endpoints (Phase 6)
# =============================================================================

class DocumentResponse(BaseModel):
    doc_id: str
    doc_type: str
    filename: str
    file_path: Optional[str]
    extracted_entities: Dict[str, Any]
    uploaded_at: str
    verification_status: Optional[str] = None


class PolicyResponse(BaseModel):
    policy_id: str
    policy_number: str
    product_line: str
    holder_name: str
    coverage_amount: float
    deductible: float
    status: str
    effective_date: str
    expiration_date: str


class CaseDetailResponse(BaseModel):
    case: CaseResponse
    claim: Dict[str, Any]
    policy: Optional[PolicyResponse]
    documents: List[DocumentResponse]
    audit_trail: List[Dict[str, Any]]


@router.get("/case/{case_id}/documents", response_model=List[DocumentResponse])
async def get_case_documents(
    case_id: UUID,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Get all documents associated with a case for specialist review."""
    case = _get_case_or_404(db, case_id)

    # Get documents for the claim
    documents = get_documents_for_claim(db, str(case.claim_id))

    return [
        DocumentResponse(
            doc_id=str(doc.get("doc_id", "")),
            doc_type=doc.get("doc_type", "unknown"),
            filename=doc.get("filename", ""),
            file_path=doc.get("file_path"),
            extracted_entities=doc.get("extracted_entities", {}),
            uploaded_at=doc.get("uploaded_at", ""),
            verification_status=doc.get("verification_status"),
        )
        for doc in documents
    ]


@router.get("/case/{case_id}/policy", response_model=Optional[PolicyResponse])
async def get_case_policy(
    case_id: UUID,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Get policy details for a case."""
    case = _get_case_or_404(db, case_id)
    claim = case.claim

    if not claim or not claim.policy:
        return None

    policy = claim.policy

    return PolicyResponse(
        policy_id=str(policy.policy_id),
        policy_number=policy.policy_number,
        product_line=policy.product_line.value if hasattr(policy.product_line, 'value') else str(policy.product_line),
        holder_name=policy.holder.name if policy.holder else "Unknown",
        coverage_amount=float(policy.coverage_amount or 0),
        deductible=float(policy.deductible or 0),
        status=policy.status.value if hasattr(policy.status, 'value') else str(policy.status),
        effective_date=policy.effective_date.isoformat() if policy.effective_date else "",
        expiration_date=policy.expiration_date.isoformat() if policy.expiration_date else "",
    )


@router.get("/case/{case_id}/full", response_model=CaseDetailResponse)
async def get_case_full_details(
    case_id: UUID,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Get complete case details including documents, policy, and audit trail."""
    case = _get_case_or_404(db, case_id)
    claim = case.claim

    # Get documents
    documents = get_documents_for_claim(db, str(case.claim_id))
    doc_responses = [
        DocumentResponse(
            doc_id=str(doc.get("doc_id", "")),
            doc_type=doc.get("doc_type", "unknown"),
            filename=doc.get("filename", ""),
            file_path=doc.get("file_path"),
            extracted_entities=doc.get("extracted_entities", {}),
            uploaded_at=doc.get("uploaded_at", ""),
            verification_status=doc.get("verification_status"),
        )
        for doc in documents
    ]

    # Get policy
    policy_response = None
    if claim and claim.policy:
        policy = claim.policy
        policy_response = PolicyResponse(
            policy_id=str(policy.policy_id),
            policy_number=policy.policy_number,
            product_line=policy.product_line.value if hasattr(policy.product_line, 'value') else str(policy.product_line),
            holder_name=policy.holder.name if policy.holder else "Unknown",
            coverage_amount=float(policy.coverage_amount or 0),
            deductible=float(policy.deductible or 0),
            status=policy.status.value if hasattr(policy.status, 'value') else str(policy.status),
            effective_date=policy.effective_date.isoformat() if policy.effective_date else "",
            expiration_date=policy.expiration_date.isoformat() if policy.expiration_date else "",
        )

    # Get audit trail
    audits = (
        db.query(CaseAudit)
        .filter(CaseAudit.case_id == case_id)
        .order_by(CaseAudit.created_at.desc())
        .limit(50)
        .all()
    )
    audit_trail = [
        {
            "event_type": a.event_type,
            "actor_type": a.actor_type.value if hasattr(a.actor_type, 'value') else str(a.actor_type),
            "actor_id": str(a.actor_id) if a.actor_id else None,
            "details": a.details or {},
            "created_at": a.created_at.isoformat(),
        }
        for a in audits
    ]

    # Build claim dict
    claim_dict = {}
    if claim:
        claim_dict = {
            "claim_id": str(claim.claim_id),
            "claim_number": claim.claim_number,
            "claim_type": claim.claim_type,
            "status": claim.status.value if hasattr(claim.status, 'value') else str(claim.status),
            "incident_date": claim.incident_date.isoformat() if claim.incident_date else None,
            "metadata": claim.metadata or {},
            "timeline": claim.timeline or [],
        }

    return CaseDetailResponse(
        case=case_to_response(case),
        claim=claim_dict,
        policy=policy_response,
        documents=doc_responses,
        audit_trail=audit_trail,
    )


@router.get("/case/{case_id}/audit-trail")
async def get_case_audit_trail(
    case_id: UUID,
    limit: int = 50,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Get audit trail for a case."""
    case = _get_case_or_404(db, case_id)

    audits = (
        db.query(CaseAudit)
        .filter(CaseAudit.case_id == case_id)
        .order_by(CaseAudit.created_at.desc())
        .limit(limit)
        .all()
    )

    return {
        "case_id": str(case_id),
        "audit_trail": [
            {
                "event_type": a.event_type,
                "actor_type": a.actor_type.value if hasattr(a.actor_type, 'value') else str(a.actor_type),
                "actor_id": str(a.actor_id) if a.actor_id else None,
                "details": a.details or {},
                "created_at": a.created_at.isoformat(),
            }
            for a in audits
        ],
    }


class AddNoteRequest(BaseModel):
    note: str
    is_internal: bool = True


@router.post("/case/{case_id}/notes")
async def add_case_note(
    case_id: UUID,
    request: AddNoteRequest,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Add an internal note to a case."""
    case = _get_case_or_404(db, case_id)
    user_id = payload.get("sub")

    # Add note to case packet
    if "notes" not in case.case_packet:
        case.case_packet["notes"] = []

    case.case_packet["notes"].append({
        "note": request.note,
        "author_id": user_id,
        "is_internal": request.is_internal,
        "created_at": datetime.utcnow().isoformat(),
    })

    # Mark case_packet as modified for SQLAlchemy
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(case, "case_packet")

    # Add audit
    audit = CaseAudit(
        case_id=case.case_id,
        event_type="note_added",
        actor_id=user_id,
        actor_type=ActorType.CELEST,
        details={"is_internal": request.is_internal},
    )
    db.add(audit)
    db.commit()

    return {"message": "Note added", "case_id": str(case_id)}


@router.get("/case/{case_id}/notes")
async def get_case_notes(
    case_id: UUID,
    payload: dict = Depends(require_role(["celest", "admin"])),
    db: Session = Depends(get_db),
):
    """Get all notes for a case."""
    case = _get_case_or_404(db, case_id)

    notes = case.case_packet.get("notes", [])

    return {"case_id": str(case_id), "notes": notes}



