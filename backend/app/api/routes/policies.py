"""
Policies API routes
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import Policy, PolicyCoverage, ProductType, PolicyStatus
from app.core import get_current_user_id, logger

router = APIRouter()


# Response schemas
class CoverageResponse(BaseModel):
    coverage_id: str
    coverage_type: str
    limit_amount: float
    deductible: float
    copay: float
    coinsurance_pct: float
    exclusions: List[str]


class PolicyResponse(BaseModel):
    policy_id: str
    policy_number: str
    product_type: str
    effective_date: str
    expiration_date: str
    status: str
    is_active: bool
    coverages: List[CoverageResponse] = []


class PolicyLookupRequest(BaseModel):
    policy_number: str


@router.get("/me", response_model=List[PolicyResponse])
async def get_my_policies(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get all policies for the current user."""
    policies = db.query(Policy).filter(Policy.user_id == user_id).all()
    
    return [
        PolicyResponse(
            policy_id=str(p.policy_id),
            policy_number=p.policy_number,
            product_type=p.product_type.value,
            effective_date=p.effective_date.isoformat(),
            expiration_date=p.expiration_date.isoformat(),
            status=p.status.value,
            is_active=p.is_active(),
            coverages=[
                CoverageResponse(
                    coverage_id=str(c.coverage_id),
                    coverage_type=c.coverage_type,
                    limit_amount=float(c.limit_amount),
                    deductible=float(c.deductible),
                    copay=float(c.copay),
                    coinsurance_pct=float(c.coinsurance_pct),
                    exclusions=c.exclusions or [],
                )
                for c in p.coverages
            ],
        )
        for p in policies
    ]


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get policy details by ID."""
    policy = db.query(Policy).filter(
        Policy.policy_id == policy_id,
        Policy.user_id == user_id,
    ).first()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )
    
    return PolicyResponse(
        policy_id=str(policy.policy_id),
        policy_number=policy.policy_number,
        product_type=policy.product_type.value,
        effective_date=policy.effective_date.isoformat(),
        expiration_date=policy.expiration_date.isoformat(),
        status=policy.status.value,
        is_active=policy.is_active(),
        coverages=[
            CoverageResponse(
                coverage_id=str(c.coverage_id),
                coverage_type=c.coverage_type,
                limit_amount=float(c.limit_amount),
                deductible=float(c.deductible),
                copay=float(c.copay),
                coinsurance_pct=float(c.coinsurance_pct),
                exclusions=c.exclusions or [],
            )
            for c in policy.coverages
        ],
    )


@router.post("/lookup", response_model=PolicyResponse)
async def lookup_policy(
    request: PolicyLookupRequest,
    db: Session = Depends(get_db),
):
    """Lookup policy by policy number (for guest flow)."""
    policy = db.query(Policy).filter(
        Policy.policy_number == request.policy_number
    ).first()
    
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )
    
    logger.info(f"Policy lookup: {request.policy_number}")
    
    return PolicyResponse(
        policy_id=str(policy.policy_id),
        policy_number=policy.policy_number,
        product_type=policy.product_type.value,
        effective_date=policy.effective_date.isoformat(),
        expiration_date=policy.expiration_date.isoformat(),
        status=policy.status.value,
        is_active=policy.is_active(),
        coverages=[
            CoverageResponse(
                coverage_id=str(c.coverage_id),
                coverage_type=c.coverage_type,
                limit_amount=float(c.limit_amount),
                deductible=float(c.deductible),
                copay=float(c.copay),
                coinsurance_pct=float(c.coinsurance_pct),
                exclusions=c.exclusions or [],
            )
            for c in policy.coverages
        ],
    )
