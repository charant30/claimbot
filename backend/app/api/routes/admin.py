"""
Admin API routes
"""
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.services.session_store import deduplicate_messages
from app.db.models import (
    SystemSettings, AuditLog, User, Case, Claim, Policy,
    CaseStatus, ClaimStatus, DocumentFlowConfig, IntentConfig, FlowRule
)
from app.core import require_role, logger, log_audit_event
from app.services import flow_config as flow_config_service

router = APIRouter()


# Request/Response schemas
class LLMSettingsRequest(BaseModel):
    llm_provider: str  # "openai", "bedrock" or "ollama"
    # OpenAI settings
    openai_api_key: Optional[str] = None
    openai_model: Optional[str] = None
    openai_vision_model: Optional[str] = None
    # Bedrock settings
    bedrock_model: Optional[str] = None
    # Ollama settings
    ollama_model: Optional[str] = None
    ollama_vision_model: Optional[str] = None
    ollama_endpoint: Optional[str] = None


class LLMSettingsResponse(BaseModel):
    llm_provider: str
    # OpenAI settings (API key is masked for security)
    openai_api_key_configured: bool
    openai_model: str
    openai_vision_model: str
    # Bedrock settings
    bedrock_model: str
    # Ollama settings
    ollama_model: str
    ollama_vision_model: str
    ollama_endpoint: str


class MetricsResponse(BaseModel):
    total_users: int
    total_claims: int
    active_cases: int
    resolved_cases: int
    claims_by_status: Dict[str, int]
    escalation_rate: float
    # Chat metrics
    active_sessions: int = 0
    total_sessions_today: int = 0
    # LLM metrics
    llm_provider: str = "unknown"
    langfuse_enabled: bool = False


class AuditLogResponse(BaseModel):
    log_id: str
    event_type: str
    resource_type: Optional[str]
    actor_type: str
    action: str
    timestamp: str


def get_setting(db: Session, key: str, default: Any = None) -> Any:
    """Get a system setting value."""
    setting = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    return setting.value if setting else default


def set_setting(db: Session, key: str, value: Any, user_id: str = None) -> None:
    """Set a system setting value."""
    setting = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    if setting:
        setting.value = value
        setting.updated_by = user_id
    else:
        setting = SystemSettings(key=key, value=value, updated_by=user_id)
        db.add(setting)
    db.commit()


@router.get("/llm-settings", response_model=LLMSettingsResponse)
async def get_llm_settings(
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Get current LLM provider settings."""
    # Check if OpenAI API key is configured (don't return the actual key)
    openai_key = get_setting(db, "openai_api_key", "")
    if not openai_key:
        from app.core.config import settings as app_settings
        openai_key = app_settings.OPENAI_API_KEY
    
    return LLMSettingsResponse(
        llm_provider=get_setting(db, "llm_provider", "openai"),
        openai_api_key_configured=bool(openai_key),
        openai_model=get_setting(db, "openai_model", "gpt-4o-mini"),
        openai_vision_model=get_setting(db, "openai_vision_model", "gpt-4o-mini"),
        bedrock_model=get_setting(db, "bedrock_model", "anthropic.claude-3-sonnet-20240229-v1:0"),
        ollama_model=get_setting(db, "ollama_model", "llama3"),
        ollama_vision_model=get_setting(db, "ollama_vision_model", "llava"),
        ollama_endpoint=get_setting(db, "ollama_endpoint", "http://localhost:11434"),
    )


@router.put("/llm-settings", response_model=LLMSettingsResponse)
async def update_llm_settings(
    request: LLMSettingsRequest,
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Update LLM provider settings."""
    user_id = payload.get("sub")
    
    if request.llm_provider not in ["openai", "bedrock", "ollama"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid LLM provider. Must be 'openai', 'bedrock' or 'ollama'",
        )
    
    set_setting(db, "llm_provider", request.llm_provider, user_id)
    
    # OpenAI settings
    if request.openai_api_key:
        set_setting(db, "openai_api_key", request.openai_api_key, user_id)
    if request.openai_model:
        set_setting(db, "openai_model", request.openai_model, user_id)
    if request.openai_vision_model:
        set_setting(db, "openai_vision_model", request.openai_vision_model, user_id)
    
    # Bedrock settings
    if request.bedrock_model:
        set_setting(db, "bedrock_model", request.bedrock_model, user_id)
    
    # Ollama settings
    if request.ollama_model:
        set_setting(db, "ollama_model", request.ollama_model, user_id)
    if request.ollama_vision_model:
        set_setting(db, "ollama_vision_model", request.ollama_vision_model, user_id)
    if request.ollama_endpoint:
        set_setting(db, "ollama_endpoint", request.ollama_endpoint, user_id)
    
    logger.info(f"LLM settings updated by {user_id}: provider={request.llm_provider}")
    
    return await get_llm_settings(payload, db)


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Get dashboard metrics including chat and LLM stats."""
    total_users = db.query(func.count(User.user_id)).scalar()
    total_claims = db.query(func.count(Claim.claim_id)).scalar()
    
    active_cases = db.query(func.count(Case.case_id)).filter(
        Case.status.in_([CaseStatus.ESCALATED, CaseStatus.AGENT_HANDLING])
    ).scalar()
    
    resolved_cases = db.query(func.count(Case.case_id)).filter(
        Case.status == CaseStatus.RESOLVED
    ).scalar()
    
    # Claims by status
    claims_by_status = {}
    for status_val in ClaimStatus:
        count = db.query(func.count(Claim.claim_id)).filter(
            Claim.status == status_val
        ).scalar()
        claims_by_status[status_val.value] = count
    
    # Escalation rate
    total_cases = db.query(func.count(Case.case_id)).scalar()
    escalation_rate = (total_cases / total_claims * 100) if total_claims > 0 else 0
    
    # Chat session metrics (from session store)
    try:
        from app.services.session_store import get_session_store
        session_store = get_session_store()
        active_sessions = session_store.count()
    except (ImportError, AttributeError) as e:
        logger.warning(f"Failed to get session count: {e}")
        active_sessions = 0
    
    # LLM provider info
    llm_provider = get_setting(db, "llm_provider", "ollama")
    
    # LangFuse status
    from app.core.config import settings
    langfuse_enabled = bool(settings.LANGFUSE_PUBLIC_KEY)
    
    return MetricsResponse(
        total_users=total_users,
        total_claims=total_claims,
        active_cases=active_cases,
        resolved_cases=resolved_cases,
        claims_by_status=claims_by_status,
        escalation_rate=round(escalation_rate, 2),
        active_sessions=active_sessions,
        total_sessions_today=active_sessions,  # Simplified for now
        llm_provider=llm_provider,
        langfuse_enabled=langfuse_enabled,
    )


# ----- Claims list and status update (for admin/Celest review and approval) -----
class ClaimListItem(BaseModel):
    claim_id: str
    claim_number: str
    policy_id: str
    status: str
    incident_date: str
    loss_amount: float
    claim_metadata: Dict[str, Any]
    created_at: str


class UpdateClaimStatusRequest(BaseModel):
    status: str  # submitted, under_review, approved, denied, paid


@router.get("/claims", response_model=List[ClaimListItem])
async def list_claims(
    status_filter: Optional[str] = None,
    limit: int = 100,
    payload: dict = Depends(require_role(["admin", "celest"])),
    db: Session = Depends(get_db),
):
    """List all claims for admin/Celest review. Optional filter by status."""
    query = db.query(Claim).order_by(Claim.created_at.desc()).limit(limit)
    if status_filter:
        try:
            query = query.filter(Claim.status == ClaimStatus(status_filter))
        except ValueError:
            pass
    claims = query.all()
    return [
        ClaimListItem(
            claim_id=str(c.claim_id),
            claim_number=c.claim_number,
            policy_id=str(c.policy_id),
            status=c.status.value,
            incident_date=c.incident_date.isoformat(),
            loss_amount=float(c.loss_amount),
            claim_metadata=c.claim_metadata or {},
            created_at=c.created_at.isoformat(),
        )
        for c in claims
    ]


@router.patch("/claims/{claim_id}")
async def update_claim_status(
    claim_id: UUID,
    request: UpdateClaimStatusRequest,
    payload: dict = Depends(require_role(["admin", "celest"])),
    db: Session = Depends(get_db),
):
    """Update claim status (e.g. approve/deny). Change is visible to customer on their dashboard."""
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
    try:
        new_status = ClaimStatus(request.status)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {[s.value for s in ClaimStatus]}",
        )
    old_status = claim.status
    claim.status = new_status
    claim.add_timeline_event(
        new_status.value,
        str(payload.get("sub", "admin")),
        f"Status updated from {old_status.value} to {new_status.value}",
    )
    db.commit()
    db.refresh(claim)
    actor = str(payload.get("sub", "admin"))
    log_audit_event(
        "claim_status_updated",
        actor,
        payload.get("role", "admin"),
        {"claim_id": str(claim_id), "old_status": old_status.value, "new_status": new_status.value},
    )
    logger.info(f"Claim {claim_id} status updated to {new_status.value} by {actor}")
    return {
        "claim_id": str(claim.claim_id),
        "claim_number": claim.claim_number,
        "status": claim.status.value,
    }


@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    limit: int = 100,
    event_type: Optional[str] = None,
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Get audit logs."""
    query = db.query(AuditLog).order_by(AuditLog.timestamp.desc())
    
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    
    logs = query.limit(limit).all()
    
    return [
        AuditLogResponse(
            log_id=str(log.log_id),
            event_type=log.event_type,
            resource_type=log.resource_type,
            actor_type=log.actor_type,
            action=log.action,
            timestamp=log.timestamp.isoformat(),
        )
        for log in logs
    ]


class SessionResponse(BaseModel):
    session_id: str
    user_id: Optional[str]
    user_name: Optional[str]
    user_email: Optional[str]
    session_type: Optional[str]
    status: Optional[str]
    thread_id: Optional[str]
    claim_draft_id: Optional[str]
    claim_number: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    last_activity_at: Optional[str]
    completed_at: Optional[str]


class TranscriptSummary(BaseModel):
    thread_id: str
    user_id: str
    policy_id: Optional[str]
    message_count: int
    created_at: str
    last_message: Optional[str] = None


class TranscriptDetail(BaseModel):
    thread_id: str
    user_id: str
    policy_id: Optional[str]
    messages: List[Dict[str, Any]]
    created_at: str


@router.get("/sessions", response_model=List[SessionResponse])
async def get_sessions(
    limit: int = 100,
    include_completed: bool = True,
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Get all chat sessions with user names for admin review."""
    from app.services.session_store import get_session_store
    session_store = get_session_store()

    # Get sessions from database-backed store
    sessions = session_store.list_all(limit=limit, include_completed=include_completed)

    return [
        SessionResponse(
            session_id=session.get("session_id", ""),
            user_id=session.get("user_id"),
            user_name=session.get("user_name"),
            user_email=session.get("user_email"),
            session_type=session.get("session_type"),
            status=session.get("status"),
            thread_id=session.get("thread_id"),
            claim_draft_id=session.get("claim_draft_id"),
            claim_number=session.get("claim_number"),
            created_at=session.get("created_at"),
            updated_at=session.get("updated_at"),
            last_activity_at=session.get("last_activity_at"),
            completed_at=session.get("completed_at"),
        )
        for session in sessions
    ]


def _canonical_thread_id(session: dict) -> str:
    """Return a canonical thread id for deduplication (same conversation may be stored under fnol:uuid or conversation_state:uuid)."""
    tid = session.get("thread_id")
    if tid:
        return tid
    sid = session.get("session_id", "")
    for prefix in ("fnol:", "conversation_state:"):
        if sid.startswith(prefix):
            return sid[len(prefix):] or sid
    return sid


@router.get("/transcripts", response_model=List[TranscriptSummary])
async def get_transcripts(
    limit: int = 50,
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Get all chat session transcripts for admin review. Deduplicated by thread so each conversation appears once."""
    from app.services.session_store import get_session_store
    session_store = get_session_store()

    sessions = session_store.list_all(limit=limit * 2)
    by_thread: dict = {}
    for session in sessions:
        canonical = _canonical_thread_id(session)
        existing = by_thread.get(canonical)
        last_activity = session.get("last_activity_at") or session.get("created_at") or ""
        existing_activity = (existing.get("last_activity_at") or existing.get("created_at") or "") if existing else ""
        if existing is None or last_activity > existing_activity:
            by_thread[canonical] = session

    result = []
    for session in list(by_thread.values())[:limit]:
        msgs = deduplicate_messages(session.get("messages", []))
        canonical = _canonical_thread_id(session)
        result.append(TranscriptSummary(
            thread_id=canonical,
            user_id=session.get("user_id", ""),
            policy_id=session.get("policy_id"),
            message_count=len(msgs),
            created_at=session.get("created_at", ""),
            last_message=msgs[-1].get("content", "")[:100] if msgs else None,
        ))
    return result


@router.get("/transcripts/{session_identifier}", response_model=TranscriptDetail)
async def get_transcript_detail(
    session_identifier: str,
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Get detailed transcript for a specific chat session.
    
    The session_identifier can be either:
    - A session_id (the key used in session store, e.g., "fnol:xxx" or "conversation_state:xxx")
    - A thread_id (for backwards compatibility)
    """
    from app.services.session_store import get_session_store
    from app.db.models import Session as DBSession
    
    session_store = get_session_store()

    # Try the identifier directly first (it might be the session_id)
    session = session_store.get(session_identifier)
    
    # If not found, search database by session_id then by thread_id
    if not session:
        try:
            db_session = db.query(DBSession).filter(DBSession.session_id == session_identifier).first()
            if not db_session and session_identifier:
                db_session = db.query(DBSession).filter(DBSession.thread_id == session_identifier).first()
            if db_session:
                session = db_session.to_dict()
        except Exception as e:
            logger.error(f"Failed to lookup session by session_id/thread_id: {e}")
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    messages = deduplicate_messages(session.get("messages", []))
    return TranscriptDetail(
        thread_id=session.get("thread_id", "") or session_identifier,
        user_id=session.get("user_id", ""),
        policy_id=session.get("policy_id"),
        messages=messages,
        created_at=session.get("created_at", ""),
    )


# =============================================================================
# Intent Configuration CRUD
# =============================================================================

class IntentConfigRequest(BaseModel):
    name: str
    display_name: str
    description: Optional[str] = None
    applicable_products: Optional[List[str]] = None
    trigger_phrases: Optional[List[str]] = None
    required_fields: Optional[List[str]] = None
    flow_config: Optional[Dict[str, Any]] = None
    icon: Optional[str] = None
    is_active: bool = True
    priority: int = 0


@router.get("/intents")
async def get_intents(
    active_only: bool = False,
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Get all configured intents."""
    intents = flow_config_service.get_all_intents(db, active_only=active_only)

    if not intents:
        # Return defaults if no database config
        return {"intents": flow_config_service.DEFAULT_INTENTS}

    return {"intents": [i.to_dict() for i in intents]}


@router.post("/intents")
async def create_intent(
    request: IntentConfigRequest,
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Create a new intent configuration."""
    existing = flow_config_service.get_intent_by_name(db, request.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Intent with name '{request.name}' already exists",
        )

    intent = flow_config_service.create_intent_config(
        db=db,
        name=request.name,
        display_name=request.display_name,
        description=request.description,
        applicable_products=request.applicable_products,
        trigger_phrases=request.trigger_phrases,
        required_fields=request.required_fields,
        flow_config=request.flow_config,
        icon=request.icon,
    )

    logger.info(f"Intent created: {intent.name} by {payload.get('sub')}")
    return intent.to_dict()


@router.put("/intents/{intent_id}")
async def update_intent(
    intent_id: str,
    request: IntentConfigRequest,
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Update an intent configuration."""
    updates = request.model_dump(exclude_unset=True)
    intent = flow_config_service.update_intent_config(db, intent_id, updates)

    if not intent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intent not found",
        )

    logger.info(f"Intent updated: {intent.name} by {payload.get('sub')}")
    return intent.to_dict()


@router.delete("/intents/{intent_id}")
async def delete_intent(
    intent_id: str,
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Delete an intent configuration."""
    success = flow_config_service.delete_intent_config(db, intent_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Intent not found",
        )

    logger.info(f"Intent deleted: {intent_id} by {payload.get('sub')}")
    return {"message": "Intent deleted"}


# =============================================================================
# Document Flow Configuration CRUD
# =============================================================================

class DocumentFlowRequest(BaseModel):
    product_line: str
    incident_type: Optional[str] = None
    document_sequence: List[str]
    conditional_rules: Optional[Dict[str, Any]] = None
    field_requirements: Optional[Dict[str, List[str]]] = None
    is_active: bool = True
    priority: int = 0


@router.get("/document-flows")
async def get_document_flows(
    product_line: Optional[str] = None,
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Get all document flow configurations."""
    query = db.query(DocumentFlowConfig)

    if product_line:
        query = query.filter(DocumentFlowConfig.product_line == product_line)

    configs = query.order_by(
        DocumentFlowConfig.product_line,
        DocumentFlowConfig.priority.desc()
    ).all()

    if not configs:
        # Return defaults if no database config
        return {
            "document_flows": [
                {
                    "product_line": pl,
                    "incident_type": it if it != "default" else None,
                    "document_sequence": docs,
                    "is_default": True,
                }
                for pl, incidents in flow_config_service.DEFAULT_DOCUMENT_FLOWS.items()
                for it, docs in incidents.items()
            ]
        }

    return {"document_flows": [c.to_dict() for c in configs]}


@router.post("/document-flows")
async def create_document_flow(
    request: DocumentFlowRequest,
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Create a new document flow configuration."""
    config = flow_config_service.create_document_flow_config(
        db=db,
        product_line=request.product_line,
        incident_type=request.incident_type,
        document_sequence=request.document_sequence,
        conditional_rules=request.conditional_rules,
        field_requirements=request.field_requirements,
        created_by=payload.get("sub"),
    )

    logger.info(f"Document flow created: {config.product_line}/{config.incident_type} by {payload.get('sub')}")
    return config.to_dict()


@router.put("/document-flows/{config_id}")
async def update_document_flow(
    config_id: str,
    request: DocumentFlowRequest,
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Update a document flow configuration."""
    updates = request.model_dump(exclude_unset=True)
    config = flow_config_service.update_document_flow_config(db, config_id, updates)

    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document flow configuration not found",
        )

    logger.info(f"Document flow updated: {config_id} by {payload.get('sub')}")
    return config.to_dict()


@router.delete("/document-flows/{config_id}")
async def delete_document_flow(
    config_id: str,
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Delete a document flow configuration."""
    success = flow_config_service.delete_document_flow_config(db, config_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document flow configuration not found",
        )

    logger.info(f"Document flow deleted: {config_id} by {payload.get('sub')}")
    return {"message": "Document flow deleted"}


# =============================================================================
# Flow Rules CRUD
# =============================================================================

class FlowRuleRequest(BaseModel):
    name: str
    description: Optional[str] = None
    conditions: Dict[str, Any]
    action: Dict[str, Any]
    is_active: bool = True
    priority: int = 0


@router.get("/flows")
async def get_flows(
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Get all flow rules and general flow settings."""
    rules = flow_config_service.get_all_flow_rules(db, active_only=False)

    # Also return general settings
    settings = {
        "confidence_threshold": get_setting(db, "confidence_threshold", 0.7),
        "auto_approval_limit": get_setting(db, "auto_approval_limit", 5000),
    }

    return {
        "settings": settings,
        "rules": [r.to_dict() for r in rules] if rules else [],
    }


@router.put("/flows/settings")
async def update_flow_settings(
    settings: Dict[str, Any],
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Update general flow settings."""
    user_id = payload.get("sub")

    if "confidence_threshold" in settings:
        set_setting(db, "confidence_threshold", settings["confidence_threshold"], user_id)
    if "auto_approval_limit" in settings:
        set_setting(db, "auto_approval_limit", settings["auto_approval_limit"], user_id)

    logger.info(f"Flow settings updated by {user_id}")
    return {"message": "Settings updated", "settings": settings}


@router.post("/flows/rules")
async def create_flow_rule(
    request: FlowRuleRequest,
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Create a new flow rule."""
    rule = flow_config_service.create_flow_rule(
        db=db,
        name=request.name,
        description=request.description,
        conditions=request.conditions,
        action=request.action,
        priority=request.priority,
    )

    logger.info(f"Flow rule created: {rule.name} by {payload.get('sub')}")
    return rule.to_dict()


@router.put("/flows/rules/{rule_id}")
async def update_flow_rule(
    rule_id: str,
    request: FlowRuleRequest,
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Update a flow rule."""
    updates = request.model_dump(exclude_unset=True)
    rule = flow_config_service.update_flow_rule(db, rule_id, updates)

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow rule not found",
        )

    logger.info(f"Flow rule updated: {rule_id} by {payload.get('sub')}")
    return rule.to_dict()


@router.delete("/flows/rules/{rule_id}")
async def delete_flow_rule(
    rule_id: str,
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Delete a flow rule."""
    success = flow_config_service.delete_flow_rule(db, rule_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flow rule not found",
        )

    logger.info(f"Flow rule deleted: {rule_id} by {payload.get('sub')}")
    return {"message": "Flow rule deleted"}
