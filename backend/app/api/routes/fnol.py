"""
FNOL (First Notice of Loss) API routes

Provides endpoints for the structured FNOL claim intake flow.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
import uuid as uuid_lib
from datetime import datetime, date as date_type

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import Policy, ClaimDraft, Claim, Case, CaseStatus
from app.db.models.claim import ClaimType, ClaimStatus
from app.db.models.fnol_enums import ClaimDraftStatus, FNOLState as FNOLStateEnum
from app.core import get_current_user_id, get_optional_user_id, logger
from app.services.session_store import get_session_store
from app.services.rate_limiter import get_rate_limiter, get_client_identifier
from app.services.db_utils import update_claim_draft_with_retry, create_claim_draft_with_retry
from app.orchestration.fnol.machine import get_fnol_machine
from app.orchestration.fnol.state import FNOLConversationState


router = APIRouter()


# ============================================================================
# Request/Response Schemas
# ============================================================================

class FNOLSessionRequest(BaseModel):
    """Request to create a new FNOL session."""
    policy_id: Optional[str] = None


class FNOLSessionResponse(BaseModel):
    """Response for session creation/retrieval."""
    thread_id: str
    claim_draft_id: str
    current_state: str
    message: str
    needs_input: bool
    input_type: str
    options: List[Dict[str, Any]] = []
    progress: Dict[str, Any] = {}
    ui_hints: Dict[str, Any] = {}


class FNOLMessageRequest(BaseModel):
    """Request to send a message in an FNOL session."""
    thread_id: str
    message: str
    metadata: Dict[str, Any] = {}


class FNOLMessageResponse(BaseModel):
    """Response from processing an FNOL message."""
    thread_id: str
    claim_draft_id: str
    current_state: str
    message: str
    needs_input: bool
    input_type: str
    options: List[Dict[str, Any]] = []
    validation_errors: List[str] = []
    progress: Dict[str, Any] = {}
    ui_hints: Dict[str, Any] = {}
    is_complete: bool = False
    should_escalate: bool = False
    escalation_reason: Optional[str] = None


class FNOLStateResponse(BaseModel):
    """Response with current FNOL state."""
    thread_id: str
    claim_draft_id: str
    status: str
    session_status: Optional[str] = "active"  # active | ended (for transcripts/Salesforce)
    ended_at: Optional[str] = None
    current_state: str
    progress_percent: int
    completed_states: List[str]
    collected_data: Dict[str, Any] = {}


class FNOLSummaryResponse(BaseModel):
    """Response with claim summary."""
    thread_id: str
    claim_draft_id: str
    summary: Dict[str, Any]
    can_submit: bool
    validation_errors: List[str] = []


class DocumentUploadResponse(BaseModel):
    """Response from document upload."""
    evidence_id: str
    evidence_type: str
    upload_status: str
    evidence_type: str
    upload_status: str
    extracted_data: Dict[str, Any] = {}


class FNOLHistoryMessage(BaseModel):
    """Message in FNOL conversation history."""
    role: str
    content: str
    timestamp: str
    message_id: Optional[str] = None


# ============================================================================
# Helper Functions
# ============================================================================

def _state_to_response(state: FNOLConversationState, is_new: bool = False) -> FNOLMessageResponse:
    """Convert FNOL state to API response."""
    ui_hints = state.get("ui_hints", {})

    return FNOLMessageResponse(
        thread_id=state["thread_id"],
        claim_draft_id=state["claim_draft_id"],
        current_state=state["current_state"],
        message=state.get("ai_response", ""),
        needs_input=state.get("needs_user_input", True),
        input_type=ui_hints.get("input_type", "text"),
        options=ui_hints.get("options", []),
        validation_errors=state.get("validation_errors", []),
        progress={
            "current": state["current_state"],
            "completed": state.get("completed_states", []),
            "percent": state.get("progress_percent", 0),
        },
        ui_hints=ui_hints,
        is_complete=state.get("is_complete", False),
        should_escalate=state.get("should_escalate", False),
        escalation_reason=state.get("escalation_reason"),
    )


def _get_session_key(thread_id: str) -> str:
    """Get session store key for FNOL session."""
    return f"fnol:{thread_id}"


def _create_fnol_escalation_case(db: Session, thread_id: str, state: FNOLConversationState) -> None:
    """
    Create a Case record when FNOL escalation is triggered.
    This ensures the case appears in the celest agent queue.
    """
    # Check if case already exists for this thread
    existing = db.query(Case).filter(
        Case.chat_thread_id == thread_id,
        Case.status.in_([CaseStatus.ESCALATED, CaseStatus.AGENT_HANDLING])
    ).first()
    if existing:
        logger.info(f"FNOL escalation case already exists for thread {thread_id}")
        return

    # Try to find the claim_id from the draft
    claim_id = None
    draft_id = state.get("claim_draft_id")
    if draft_id:
        draft = db.query(ClaimDraft).filter(ClaimDraft.claim_draft_id == draft_id).first()
        if draft and draft.claim_id:
            claim_id = draft.claim_id

    # Build case packet from FNOL state
    escalation_record = state.get("state_data", {}).get("escalation_record", {})
    case_packet = {
        "escalation_reason": state.get("escalation_reason", "User requested specialist"),
        "escalation_type": escalation_record.get("type", "user_request"),
        "claim_draft_id": draft_id,
        "claim_number": state.get("claim_number"),
        "fnol_state": state.get("current_state"),
        "completed_states": state.get("completed_states", []),
        "user_id": state.get("user_id"),
    }

    # Add policy info if available
    policy_match = state.get("policy_match", {})
    if policy_match:
        case_packet["policy_number"] = policy_match.get("policy_number")
        case_packet["first_name"] = policy_match.get("holder_first_name")
        case_packet["last_name"] = policy_match.get("holder_last_name")

    case = Case(
        claim_id=claim_id,
        chat_thread_id=thread_id,
        status=CaseStatus.ESCALATED,
        stage="escalated",
        priority=3 if escalation_record.get("priority") != "critical" else 1,
        case_packet=case_packet,
    )
    db.add(case)
    db.commit()
    logger.info(f"Created FNOL escalation case {case.case_id} for thread {thread_id}")


def _convert_fnol_draft_to_claim(
    db: Session,
    claim_draft_id: str,
    state: FNOLConversationState,
    claim_number: str,
) -> Optional[Claim]:
    """
    Create a Claim from submitted FNOL state and link it to the ClaimDraft.

    So the submission appears in the database and is visible to customer (get_my_claims),
    adjuster, and admin. Returns the created Claim or None if conversion failed.
    """
    draft = db.query(ClaimDraft).filter(
        ClaimDraft.claim_draft_id == claim_draft_id,
    ).first()

    if not draft:
        logger.warning(f"ClaimDraft not found for conversion: {claim_draft_id}")
        return None
    if draft.claim_id:
        # Already converted
        return db.query(Claim).filter(Claim.claim_id == draft.claim_id).first()

    # We need a policy to create a claim (Claim.policy_id is required)
    policy_id = draft.policy_id
    if not policy_id:
        logger.warning(f"ClaimDraft {claim_draft_id} has no policy_id; cannot create Claim")
        # Still mark draft as submitted and set claim_number so user sees confirmation
        update_claim_draft_with_retry(db, claim_draft_id, {
            "status": ClaimDraftStatus.SUBMITTED,
            "claim_number": claim_number,
            "submitted_at": datetime.utcnow(),
        })
        return None

    incident = state.get("incident", {})
    incident_date = draft.incident_date
    if not incident_date and incident.get("date"):
        try:
            incident_date = date_type.fromisoformat(incident["date"])
        except (ValueError, TypeError):
            incident_date = date_type.today()

    claim_metadata = {
        "description": draft.incident_description or incident.get("description"),
        "location": incident.get("location_raw") or incident.get("location_normalized"),
        "loss_type": incident.get("loss_type"),
        "time": incident.get("time"),
        "vehicles": state.get("vehicles", []),
        "parties": state.get("parties", []),
        "injuries": state.get("injuries", []),
        "damages": state.get("damages", []),
        "evidence": state.get("evidence", []),
        "triage_route": draft.triage_route.value if draft.triage_route else None,
    }
    # Add estimated loss from damages if present
    damages = state.get("damages", [])
    if damages:
        total = sum(
            float(d.get("estimated_amount") or 0)
            for d in damages
            if d.get("estimated_amount") is not None
        )
        if total:
            claim_metadata["estimated_loss"] = total

    claim = Claim(
        policy_id=policy_id,
        claim_number=claim_number,
        claim_type=ClaimType.INCIDENT,
        status=ClaimStatus.SUBMITTED,
        incident_date=incident_date,
        loss_amount=claim_metadata.get("estimated_loss") or 0,
        claim_metadata=claim_metadata,
        timeline=[{
            "status": "submitted",
            "timestamp": datetime.utcnow().isoformat(),
            "actor": str(draft.user_id) if draft.user_id else "guest",
            "notes": "Claim submitted via FNOL",
        }],
    )
    db.add(claim)
    db.flush()

    updates = {
        "status": ClaimDraftStatus.CONVERTED,
        "claim_id": claim.claim_id,
        "claim_number": claim_number,
        "submitted_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    if not update_claim_draft_with_retry(db, claim_draft_id, updates):
        logger.warning(f"Failed to update ClaimDraft {claim_draft_id} after creating Claim")
    logger.info(f"FNOL draft {claim_draft_id} converted to Claim {claim.claim_id} ({claim_number})")
    return claim


# ============================================================================
# Routes
# ============================================================================

@router.post("/session", response_model=FNOLSessionResponse)
async def create_fnol_session(
    request: FNOLSessionRequest,
    http_request: Request,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
):
    """
    Start a new FNOL session.

    Creates a new claim intake session and returns the initial state
    with the first question (safety check).
    """
    # Rate limiting
    rate_limiter = get_rate_limiter()
    client_id = get_client_identifier(http_request, user_id)
    rate_limiter.check("fnol_session", client_id)

    session_store = get_session_store()
    fnol_machine = get_fnol_machine()
    thread_id = str(uuid_lib.uuid4())

    # Validate policy if provided
    policy_id = None
    if request.policy_id and user_id:
        policy = db.query(Policy).filter(
            Policy.policy_id == request.policy_id,
            Policy.user_id == user_id,
        ).first()
        if policy:
            policy_id = str(policy.policy_id)

    # Create session state
    state = fnol_machine.create_session(
        thread_id=thread_id,
        user_id=user_id,
        policy_id=policy_id,
    )
    state["session_status"] = "active"
    state["ended_at"] = None

    # Store session
    session_store.set(_get_session_key(thread_id), state, ttl_hours=48)

    # Create claim draft record in database with retry logic
    claim_draft = ClaimDraft(
        claim_draft_id=state["claim_draft_id"],
        thread_id=thread_id,
        user_id=user_id,
        policy_id=policy_id,
        status=ClaimDraftStatus.IN_PROGRESS,
        current_state=FNOLStateEnum.SAFETY_CHECK,
    )
    if not create_claim_draft_with_retry(db, claim_draft):
        logger.error(f"Failed to create claim draft record for thread {thread_id}")
        # Continue anyway - session is in memory store

    logger.info(f"FNOL session created: {thread_id}, draft: {state['claim_draft_id']}")

    ui_hints = state.get("ui_hints", {})
    return FNOLSessionResponse(
        thread_id=thread_id,
        claim_draft_id=state["claim_draft_id"],
        current_state=state["current_state"],
        message=state.get("ai_response", ""),
        needs_input=True,
        input_type=ui_hints.get("input_type", "yesno"),
        options=ui_hints.get("options", []),
        progress={
            "current": state["current_state"],
            "completed": [],
            "percent": 0,
        },
        ui_hints=ui_hints,
    )


@router.post("/message", response_model=FNOLMessageResponse)
async def process_fnol_message(
    request: FNOLMessageRequest,
    http_request: Request,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
):
    """
    Process a message in an FNOL session.

    Advances the state machine based on user input and returns
    the next question or confirmation.
    """
    # Rate limiting
    rate_limiter = get_rate_limiter()
    client_id = get_client_identifier(http_request, user_id)
    rate_limiter.check("fnol_message", client_id)

    session_store = get_session_store()
    fnol_machine = get_fnol_machine()

    # Get session state
    session_key = _get_session_key(request.thread_id)
    state = session_store.get(session_key)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired",
        )

    if state.get("session_status") == "ended":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This session has ended. Please start a new claim.",
        )

    # Verify authorization (if authenticated)
    if user_id and state.get("user_id") and state["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this session",
        )

    # Process message through state machine
    try:
        updated_state = await fnol_machine.process_message(state, request.message)
    except Exception as e:
        logger.error(f"Error processing FNOL message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing your response. Please try again.",
        )

    # Update session store
    session_store.set(session_key, updated_state, ttl_hours=48)

    # Update claim draft in database with retry logic
    updates = {
        "current_state": FNOLStateEnum(updated_state["current_state"]),
        "updated_at": datetime.utcnow(),
    }

    # Add incident data if present
    incident = updated_state.get("incident", {})
    if incident.get("loss_type"):
        from app.db.models.fnol_enums import LossType
        try:
            updates["loss_type"] = LossType(incident["loss_type"])
        except ValueError:
            pass

    if incident.get("date"):
        from datetime import date as date_type
        try:
            updates["incident_date"] = date_type.fromisoformat(incident["date"])
        except ValueError:
            pass

    if incident.get("location_raw"):
        updates["incident_location_raw"] = incident["location_raw"]

    if incident.get("description"):
        updates["incident_description"] = incident["description"]

    # Persist policy_id and user_id from identity match so Claim can be created on submit
    policy_match = updated_state.get("policy_match", {})
    policy_id_val = policy_match.get("policy_id")
    if policy_id_val:
        try:
            updates["policy_id"] = UUID(str(policy_id_val))
        except (TypeError, ValueError):
            # Demo/simulate may return non-UUID (e.g. "demo-policy-id"); look up by policy_number
            policy_number = policy_match.get("policy_number")
            if policy_number:
                policy = db.query(Policy).filter(Policy.policy_number == policy_number).first()
                if policy:
                    updates["policy_id"] = policy.policy_id
    if updated_state.get("user_id") is not None:
        updates["user_id"] = updated_state["user_id"]

    # Check for completion
    if updated_state.get("is_complete"):
        updates["status"] = ClaimDraftStatus.PENDING_REVIEW

    if not update_claim_draft_with_retry(db, updated_state["claim_draft_id"], updates):
        logger.warning(f"Failed to update claim draft {updated_state['claim_draft_id']} in database")

    # When user has just submitted (reached NEXT_STEPS with claim_number), persist a real Claim
    # so it appears in DB, adjuster, and admin.
    if (
        updated_state.get("claim_number")
        and updated_state.get("current_state") == "NEXT_STEPS"
    ):
        draft_id = updated_state["claim_draft_id"]
        draft = db.query(ClaimDraft).filter(ClaimDraft.claim_draft_id == draft_id).first()
        if draft and not draft.claim_id:
            _convert_fnol_draft_to_claim(
                db,
                draft_id,
                updated_state,
                updated_state["claim_number"],
            )

    # Auto-create Case in DB when FNOL escalation is triggered
    if updated_state.get("should_escalate"):
        try:
            _create_fnol_escalation_case(db, request.thread_id, updated_state)
        except Exception as case_err:
            logger.error(f"Failed to create FNOL escalation case: {case_err}")

    logger.info(f"FNOL message processed: thread={request.thread_id}, state={updated_state['current_state']}")

    return _state_to_response(updated_state)


@router.get("/session/{thread_id}/state", response_model=FNOLStateResponse)
async def get_fnol_state(
    thread_id: str,
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """
    Get the current state of an FNOL session.

    Returns the current position in the flow and collected data.
    """
    session_store = get_session_store()
    session_key = _get_session_key(thread_id)
    state = session_store.get(session_key)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired",
        )

    if user_id and state.get("user_id") and state["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this session",
        )

    session_status = state.get("session_status", "active")
    return FNOLStateResponse(
        thread_id=thread_id,
        claim_draft_id=state["claim_draft_id"],
        status="in_progress" if not state.get("is_complete") else "complete",
        session_status=session_status,
        ended_at=state.get("ended_at"),
        current_state=state["current_state"],
        progress_percent=state.get("progress_percent", 0),
        completed_states=state.get("completed_states", []),
        collected_data={
            "policy_match": state.get("policy_match", {}),
            "incident": state.get("incident", {}),
            "vehicles_count": len(state.get("vehicles", [])),
            "parties_count": len(state.get("parties", [])),
            "has_injuries": any(
                i.get("severity") != "none"
                for i in state.get("injuries", [])
            ),
        },
    )


@router.get("/session/{thread_id}/summary", response_model=FNOLSummaryResponse)
async def get_fnol_summary(
    thread_id: str,
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """
    Get a summary of the claim for review before submission.

    Returns all collected data in a human-readable format.
    """
    session_store = get_session_store()
    session_key = _get_session_key(thread_id)
    state = session_store.get(session_key)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired",
        )

    if user_id and state.get("user_id") and state["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this session",
        )

    # Build summary
    incident = state.get("incident", {})
    policy_match = state.get("policy_match", {})
    vehicles = state.get("vehicles", [])
    parties = state.get("parties", [])
    injuries = state.get("injuries", [])
    damages = state.get("damages", [])

    summary = {
        "policy": {
            "matched": policy_match.get("status") == "matched",
            "policy_number": policy_match.get("policy_number"),
            "holder_name": policy_match.get("holder_name"),
        },
        "incident": {
            "type": incident.get("loss_type"),
            "date": incident.get("date"),
            "time": incident.get("time"),
            "location": incident.get("location_raw") or incident.get("location_normalized"),
            "description": incident.get("description"),
        },
        "vehicles": [
            {
                "role": v.get("role"),
                "year": v.get("year"),
                "make": v.get("make"),
                "model": v.get("model"),
                "drivable": v.get("drivable"),
            }
            for v in vehicles
        ],
        "parties": [
            {
                "role": p.get("role"),
                "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or "Unknown",
            }
            for p in parties
        ],
        "injuries": {
            "count": len([i for i in injuries if i.get("severity") != "none"]),
            "severe_count": len([i for i in injuries if i.get("severity") in ["severe", "fatal"]]),
        },
        "damages": {
            "count": len(damages),
            "areas": list(set(d.get("damage_area") for d in damages if d.get("damage_area"))),
        },
    }

    # Validate completeness
    errors = []
    if not incident.get("loss_type"):
        errors.append("Incident type is required")
    if not incident.get("date"):
        errors.append("Incident date is required")
    if not vehicles:
        errors.append("At least one vehicle is required")

    return FNOLSummaryResponse(
        thread_id=thread_id,
        claim_draft_id=state["claim_draft_id"],
        summary=summary,
        can_submit=len(errors) == 0,
        validation_errors=errors,
    )


@router.post("/session/{thread_id}/document", response_model=DocumentUploadResponse)
async def upload_document(
    thread_id: str,
    http_request: Request,
    file: UploadFile = File(...),
    evidence_type: str = "photo",
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
):
    """
    Upload a document or photo for the FNOL claim.

    Supported types: photo, police_report, witness_statement
    """
    # Rate limiting
    rate_limiter = get_rate_limiter()
    client_id = get_client_identifier(http_request, user_id)
    rate_limiter.check("fnol_document", client_id)

    session_store = get_session_store()
    session_key = _get_session_key(thread_id)
    state = session_store.get(session_key)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired",
        )

    if user_id and state.get("user_id") and state["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this session",
        )

    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed: {', '.join(allowed_types)}",
        )

    # Generate evidence ID
    evidence_id = str(uuid_lib.uuid4())

    # In a real implementation, would upload to S3/blob storage
    # and potentially run OCR/AI extraction
    extracted_data = {}

    # Add evidence to state
    evidence_list = state.get("evidence", [])
    evidence_list.append({
        "evidence_id": evidence_id,
        "evidence_type": evidence_type,
        "upload_status": "uploaded",
        "filename": file.filename,
    })
    state["evidence"] = evidence_list

    # Update session
    session_store.set(session_key, state, ttl_hours=48)

    logger.info(f"Document uploaded: {evidence_id} for session {thread_id}")

    return DocumentUploadResponse(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        upload_status="uploaded",
        extracted_data=extracted_data,
    )


@router.post("/session/{thread_id}/end")
async def end_fnol_session(
    thread_id: str,
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """
    End an FNOL session explicitly.

    Marks the session as ended so it shows as inactive/ended in transcripts and
    integrations (e.g. Salesforce). The customer must start a new session to continue.
    """
    session_store = get_session_store()
    session_key = _get_session_key(thread_id)
    state = session_store.get(session_key)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired",
        )

    if user_id and state.get("user_id") and state["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this session",
        )

    if state.get("session_status") == "ended":
        return {"status": "ended", "thread_id": thread_id, "message": "Session already ended."}

    state["session_status"] = "ended"
    state["ended_at"] = datetime.utcnow().isoformat()
    state["status"] = "completed"  # for DB persist (SessionStatus.COMPLETED)
    session_store.set(session_key, state, ttl_hours=48)

    logger.info(f"FNOL session ended by user: thread={thread_id}")
    return {"status": "ended", "thread_id": thread_id, "message": "Session ended."}


@router.post("/session/{thread_id}/resume", response_model=FNOLSessionResponse)
async def resume_fnol_session(
    thread_id: str,
    user_id: Optional[str] = Depends(get_optional_user_id),
    db: Session = Depends(get_db),
):
    """
    Resume an abandoned FNOL session.

    Returns the current state so the user can continue where they left off.
    """
    session_store = get_session_store()
    session_key = _get_session_key(thread_id)
    state = session_store.get(session_key)

    if not state:
        # Try to restore from database
        claim_draft = db.query(ClaimDraft).filter(
            ClaimDraft.thread_id == thread_id,
        ).first()

        if not claim_draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        if claim_draft.status == ClaimDraftStatus.ABANDONED:
            claim_draft.status = ClaimDraftStatus.IN_PROGRESS
            db.commit()

        # Would need to reconstruct state from database
        # For now, return error
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Session expired. Please start a new claim.",
        )

    if user_id and state.get("user_id") and state["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this session",
        )

    if state.get("session_status") == "ended":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This session has ended. Please start a new claim.",
        )

    # Refresh TTL
    session_store.set(session_key, state, ttl_hours=48)

    ui_hints = state.get("ui_hints", {})
    return FNOLSessionResponse(
        thread_id=thread_id,
        claim_draft_id=state["claim_draft_id"],
        current_state=state["current_state"],
        message=state.get("ai_response", "Welcome back! Let's continue where you left off."),
        needs_input=state.get("needs_user_input", True),
        input_type=ui_hints.get("input_type", "text"),
        options=ui_hints.get("options", []),
        progress={
            "current": state["current_state"],
            "completed": state.get("completed_states", []),
            "percent": state.get("progress_percent", 0),
        },
        ui_hints=ui_hints,
    )


@router.get("/session/{thread_id}/messages", response_model=List[FNOLHistoryMessage])
async def get_fnol_messages(
    thread_id: str,
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """
    Get the message history for an FNOL session.
    
    Used for polling to see new agent messages.
    """
    session_store = get_session_store()
    session_key = _get_session_key(thread_id)
    state = session_store.get(session_key)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired",
        )

    if user_id and state.get("user_id") and state["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this session",
        )

    messages = state.get("messages", [])
    
    # Ensure all messages have IDs
    history = []
    for msg in messages:
        if not msg.get("message_id"):
            msg["message_id"] = str(uuid_lib.uuid4())
        
        history.append(FNOLHistoryMessage(
            role=msg["role"],
            content=msg["content"],
            timestamp=msg.get("timestamp", datetime.utcnow().isoformat()),
            message_id=msg["message_id"]
        ))
        
    return history


class FNOLEscalationMessageRequest(BaseModel):
    """Request to send a customer message during escalation."""
    thread_id: str
    message: str


@router.post("/session/{thread_id}/escalation-message")
async def send_escalation_message(
    thread_id: str,
    request: FNOLEscalationMessageRequest,
    user_id: Optional[str] = Depends(get_optional_user_id),
):
    """
    Send a customer message during escalation.
    Bypasses the state machine and writes directly to the session store
    so the agent can see it.
    """
    session_store = get_session_store()
    session_key = _get_session_key(thread_id)
    state = session_store.get(session_key)

    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or expired",
        )

    if user_id and state.get("user_id") and state["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this session",
        )

    # Append user message directly to session messages
    message_entry = {
        "message_id": str(uuid_lib.uuid4()),
        "role": "user",
        "content": request.message,
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": {"during_escalation": True},
    }
    
    messages = state.get("messages", [])
    messages.append(message_entry)
    state["messages"] = messages
    session_store.set(session_key, state, ttl_hours=48)

    logger.info(f"Customer escalation message stored for thread {thread_id}")

    return {"status": "sent", "message_id": message_entry["message_id"]}
