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
from app.db.models import (
    SystemSettings, AuditLog, User, Case, Claim, 
    CaseStatus, ClaimStatus
)
from app.core import require_role, logger

router = APIRouter()


# Request/Response schemas
class LLMSettingsRequest(BaseModel):
    llm_provider: str  # "bedrock" or "ollama"
    bedrock_model: Optional[str] = None
    ollama_model: Optional[str] = None
    ollama_endpoint: Optional[str] = None


class LLMSettingsResponse(BaseModel):
    llm_provider: str
    bedrock_model: str
    ollama_model: str
    ollama_endpoint: str


class MetricsResponse(BaseModel):
    total_users: int
    total_claims: int
    active_cases: int
    resolved_cases: int
    claims_by_status: Dict[str, int]
    escalation_rate: float


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
    return LLMSettingsResponse(
        llm_provider=get_setting(db, "llm_provider", "ollama"),
        bedrock_model=get_setting(db, "bedrock_model", "anthropic.claude-3-sonnet-20240229-v1:0"),
        ollama_model=get_setting(db, "ollama_model", "llama3"),
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
    
    if request.llm_provider not in ["bedrock", "ollama"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid LLM provider. Must be 'bedrock' or 'ollama'",
        )
    
    set_setting(db, "llm_provider", request.llm_provider, user_id)
    
    if request.bedrock_model:
        set_setting(db, "bedrock_model", request.bedrock_model, user_id)
    if request.ollama_model:
        set_setting(db, "ollama_model", request.ollama_model, user_id)
    if request.ollama_endpoint:
        set_setting(db, "ollama_endpoint", request.ollama_endpoint, user_id)
    
    logger.info(f"LLM settings updated by {user_id}: provider={request.llm_provider}")
    
    return await get_llm_settings(payload, db)


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Get dashboard metrics."""
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
    
    return MetricsResponse(
        total_users=total_users,
        total_claims=total_claims,
        active_cases=active_cases,
        resolved_cases=resolved_cases,
        claims_by_status=claims_by_status,
        escalation_rate=round(escalation_rate, 2),
    )


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


@router.get("/transcripts")
async def get_transcripts(
    limit: int = 50,
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Get chat transcripts (placeholder)."""
    # TODO: Implement full transcript retrieval
    return {"message": "Transcript endpoint - to be integrated with chat service"}


@router.get("/intents")
async def get_intents(
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Get configured intents."""
    intents = get_setting(db, "intents", [
        {"name": "file_claim", "description": "File a new claim"},
        {"name": "check_status", "description": "Check claim status"},
        {"name": "coverage_question", "description": "Ask about coverage"},
        {"name": "billing", "description": "Billing inquiry"},
    ])
    return {"intents": intents}


@router.get("/flows")
async def get_flows(
    payload: dict = Depends(require_role(["admin"])),
    db: Session = Depends(get_db),
):
    """Get configured flow rules."""
    flows = get_setting(db, "flows", {
        "confidence_threshold": 0.7,
        "auto_approval_limit": 5000,
        "escalation_triggers": [
            "low_confidence",
            "high_amount",
            "user_request",
            "coverage_ambiguity",
        ],
    })
    return {"flows": flows}
