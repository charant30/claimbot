"""
Claims API routes
"""
from datetime import date
from typing import List, Optional, Dict, Any
from uuid import UUID
import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import Claim, ClaimType, ClaimStatus, Policy
from app.core import get_current_user_id, logger, log_audit_event

router = APIRouter()


# Request/Response schemas
class CreateClaimRequest(BaseModel):
    policy_id: str
    claim_type: str  # "incident" or "medical"
    incident_date: str
    metadata: Dict[str, Any] = {}

    @field_validator("claim_type")
    @classmethod
    def validate_claim_type(cls, v: str) -> str:
        valid_types = [ct.value for ct in ClaimType]
        if v not in valid_types:
            raise ValueError(f"claim_type must be one of: {', '.join(valid_types)}")
        return v

    @field_validator("incident_date")
    @classmethod
    def validate_incident_date(cls, v: str) -> str:
        try:
            parsed_date = date.fromisoformat(v)
            # Ensure date is not in the future
            if parsed_date > date.today():
                raise ValueError("incident_date cannot be in the future")
            return v
        except ValueError as e:
            if "cannot be in the future" in str(e):
                raise
            raise ValueError("incident_date must be in ISO format (YYYY-MM-DD)")


class UpdateClaimRequest(BaseModel):
    status: Optional[str] = None
    loss_amount: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid_statuses = [cs.value for cs in ClaimStatus]
            if v not in valid_statuses:
                raise ValueError(f"status must be one of: {', '.join(valid_statuses)}")
        return v

    @field_validator("loss_amount")
    @classmethod
    def validate_loss_amount(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("loss_amount cannot be negative")
        return v


class ClaimResponse(BaseModel):
    claim_id: str
    claim_number: str
    policy_id: str
    claim_type: str
    status: str
    incident_date: str
    loss_amount: float
    reserves: float
    paid_amount: float
    timeline: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    created_at: str


def generate_claim_number(claim_type: ClaimType) -> str:
    """Generate a unique claim number."""
    prefix = "INC" if claim_type == ClaimType.INCIDENT else "MED"
    random_part = str(uuid_lib.uuid4())[:8].upper()
    return f"{prefix}-{random_part}"


@router.post("/", response_model=ClaimResponse)
async def create_claim(
    request: CreateClaimRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create a new claim (FNOL or medical intake)."""
    # Validate policy ownership
    policy = db.query(Policy).filter(
        Policy.policy_id == request.policy_id,
        Policy.user_id == user_id,
    ).first()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found or not authorized",
        )
    
    if not policy.is_active():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Policy is not active",
        )
    
    # Create claim
    claim_type = ClaimType(request.claim_type)
    claim = Claim(
        policy_id=policy.policy_id,
        claim_number=generate_claim_number(claim_type),
        claim_type=claim_type,
        incident_date=date.fromisoformat(request.incident_date),
        metadata=request.metadata,
        timeline=[],
    )
    claim.add_timeline_event("created", user_id, "Claim initiated")
    
    db.add(claim)
    db.commit()
    db.refresh(claim)
    
    log_audit_event(
        "claim_created",
        user_id,
        "user",
        {"claim_id": str(claim.claim_id), "claim_number": claim.claim_number},
    )
    
    return ClaimResponse(
        claim_id=str(claim.claim_id),
        claim_number=claim.claim_number,
        policy_id=str(claim.policy_id),
        claim_type=claim.claim_type.value,
        status=claim.status.value,
        incident_date=claim.incident_date.isoformat(),
        loss_amount=float(claim.loss_amount),
        reserves=float(claim.reserves),
        paid_amount=float(claim.paid_amount),
        timeline=claim.timeline,
        metadata=claim.metadata,
        created_at=claim.created_at.isoformat(),
    )


@router.get("/", response_model=List[ClaimResponse])
async def get_my_claims(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get all claims for the current user."""
    claims = (
        db.query(Claim)
        .join(Policy)
        .filter(Policy.user_id == user_id)
        .order_by(Claim.created_at.desc())
        .all()
    )
    
    return [
        ClaimResponse(
            claim_id=str(c.claim_id),
            claim_number=c.claim_number,
            policy_id=str(c.policy_id),
            claim_type=c.claim_type.value,
            status=c.status.value,
            incident_date=c.incident_date.isoformat(),
            loss_amount=float(c.loss_amount),
            reserves=float(c.reserves),
            paid_amount=float(c.paid_amount),
            timeline=c.timeline or [],
            metadata=c.metadata or {},
            created_at=c.created_at.isoformat(),
        )
        for c in claims
    ]


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(
    claim_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get claim details by ID."""
    claim = (
        db.query(Claim)
        .join(Policy)
        .filter(Claim.claim_id == claim_id, Policy.user_id == user_id)
        .first()
    )
    
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )
    
    return ClaimResponse(
        claim_id=str(claim.claim_id),
        claim_number=claim.claim_number,
        policy_id=str(claim.policy_id),
        claim_type=claim.claim_type.value,
        status=claim.status.value,
        incident_date=claim.incident_date.isoformat(),
        loss_amount=float(claim.loss_amount),
        reserves=float(claim.reserves),
        paid_amount=float(claim.paid_amount),
        timeline=claim.timeline or [],
        metadata=claim.metadata or {},
        created_at=claim.created_at.isoformat(),
    )


@router.patch("/{claim_id}", response_model=ClaimResponse)
async def update_claim(
    claim_id: UUID,
    request: UpdateClaimRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Update claim details."""
    claim = (
        db.query(Claim)
        .join(Policy)
        .filter(Claim.claim_id == claim_id, Policy.user_id == user_id)
        .first()
    )
    
    if not claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Claim not found",
        )
    
    if request.status:
        old_status = claim.status.value
        claim.status = ClaimStatus(request.status)
        claim.add_timeline_event(request.status, user_id, f"Status changed from {old_status}")
    
    if request.loss_amount is not None:
        claim.loss_amount = request.loss_amount
    
    if request.metadata:
        claim.metadata = {**(claim.metadata or {}), **request.metadata}
    
    db.commit()
    db.refresh(claim)
    
    log_audit_event(
        "claim_updated",
        user_id,
        "user",
        {"claim_id": str(claim.claim_id)},
    )
    
    return ClaimResponse(
        claim_id=str(claim.claim_id),
        claim_number=claim.claim_number,
        policy_id=str(claim.policy_id),
        claim_type=claim.claim_type.value,
        status=claim.status.value,
        incident_date=claim.incident_date.isoformat(),
        loss_amount=float(claim.loss_amount),
        reserves=float(claim.reserves),
        paid_amount=float(claim.paid_amount),
        timeline=claim.timeline or [],
        metadata=claim.metadata or {},
        created_at=claim.created_at.isoformat(),
    )
