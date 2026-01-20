"""
LangGraph Tools for Claims Processing
"""
from typing import Optional
from decimal import Decimal

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.db.models import Policy, Claim, Provider, ClaimType, ClaimStatus
from app.services.calculation import calculate_incident_payout, adjudicate_medical_claim


@tool
def get_policy_details(policy_id: str, db: Session) -> dict:
    """
    Get policy details including coverages.
    
    Args:
        policy_id: UUID of the policy
        db: Database session
        
    Returns:
        Policy details with coverages
    """
    policy = db.query(Policy).filter(Policy.policy_id == policy_id).first()
    if not policy:
        return {"error": "Policy not found"}
    
    return {
        "policy_id": str(policy.policy_id),
        "policy_number": policy.policy_number,
        "product_type": policy.product_type.value,
        "status": policy.status.value,
        "is_active": policy.is_active(),
        "coverages": [
            {
                "type": c.coverage_type,
                "limit": float(c.limit_amount),
                "deductible": float(c.deductible),
                "copay": float(c.copay),
                "coinsurance": float(c.coinsurance_pct),
            }
            for c in policy.coverages
        ],
    }


@tool
def get_claim_status(claim_id: str, db: Session) -> dict:
    """
    Get current claim status and timeline.
    
    Args:
        claim_id: UUID of the claim
        db: Database session
        
    Returns:
        Claim status and timeline
    """
    claim = db.query(Claim).filter(Claim.claim_id == claim_id).first()
    if not claim:
        return {"error": "Claim not found"}
    
    return {
        "claim_id": str(claim.claim_id),
        "claim_number": claim.claim_number,
        "status": claim.status.value,
        "incident_date": claim.incident_date.isoformat(),
        "loss_amount": float(claim.loss_amount),
        "paid_amount": float(claim.paid_amount),
        "timeline": claim.timeline or [],
    }


@tool
def calculate_incident_claim_payout(
    loss_amount: float,
    coverage_type: str,
    policy_id: str,
    incident_type: str,
    db: Session,
) -> dict:
    """
    Calculate payout for an incident claim using deterministic engine.
    
    Args:
        loss_amount: Total claimed loss amount
        coverage_type: Type of coverage (collision, comprehensive, dwelling, etc.)
        policy_id: UUID of the policy
        incident_type: Type of incident
        db: Database session
        
    Returns:
        Payout calculation result
    """
    policy = db.query(Policy).filter(Policy.policy_id == policy_id).first()
    if not policy:
        return {"error": "Policy not found"}
    
    # Find matching coverage
    coverage = None
    for c in policy.coverages:
        if c.coverage_type == coverage_type:
            coverage = c
            break
    
    if not coverage:
        return {"error": f"Coverage type '{coverage_type}' not found on policy"}
    
    result = calculate_incident_payout(
        loss_amount=Decimal(str(loss_amount)),
        deductible=coverage.deductible,
        coverage_limit=coverage.limit_amount,
        exclusions=coverage.exclusions or [],
        incident_type=incident_type,
    )
    
    return {
        "loss_amount": float(result.loss_amount),
        "deductible_applied": float(result.deductible_applied),
        "coverage_limit": float(result.coverage_limit),
        "payout_amount": float(result.payout_amount),
        "is_total_loss": result.is_total_loss,
        "exclusions_applied": result.exclusions_applied,
        "breakdown": result.breakdown,
    }


@tool
def calculate_medical_claim_payout(
    billed_amount: float,
    provider_npi: str,
    procedure_code: str,
    policy_id: str,
    db: Session,
) -> dict:
    """
    Calculate payout for a medical claim using deterministic engine.
    
    Args:
        billed_amount: Amount billed by provider
        provider_npi: Provider's NPI
        procedure_code: CPT procedure code
        policy_id: UUID of the policy
        db: Database session
        
    Returns:
        Medical adjudication result
    """
    policy = db.query(Policy).filter(Policy.policy_id == policy_id).first()
    if not policy:
        return {"error": "Policy not found"}
    
    # Get provider for network status and allowed amount
    provider = db.query(Provider).filter(Provider.npi == provider_npi).first()
    
    is_in_network = provider.network_status.value != "out_of_network" if provider else False
    allowed_amount = provider.get_allowed_amount(procedure_code) if provider else 0.0
    
    # Find hospital/physician coverage
    coverage = None
    for c in policy.coverages:
        if c.coverage_type in ["hospital", "physician"]:
            coverage = c
            break
    
    if not coverage:
        return {"error": "Medical coverage not found on policy"}
    
    # TODO: Track deductible across claims (simplified for demo)
    deductible_remaining = coverage.deductible
    
    result = adjudicate_medical_claim(
        billed_amount=Decimal(str(billed_amount)),
        allowed_amount=Decimal(str(allowed_amount)),
        copay=coverage.copay,
        deductible_remaining=deductible_remaining,
        coinsurance_pct=coverage.coinsurance_pct,
        coverage_limit=coverage.limit_amount,
        is_in_network=is_in_network,
    )
    
    return {
        "billed_amount": float(result.billed_amount),
        "allowed_amount": float(result.allowed_amount),
        "copay": float(result.copay),
        "deductible_applied": float(result.deductible_applied),
        "coinsurance_amount": float(result.coinsurance_amount),
        "member_responsibility": float(result.member_responsibility),
        "payer_responsibility": float(result.payer_responsibility),
        "is_in_network": result.is_in_network,
        "breakdown": result.breakdown,
    }


@tool
def check_provider_network(provider_npi: str, db: Session) -> dict:
    """
    Check if a provider is in-network.
    
    Args:
        provider_npi: Provider's NPI
        db: Database session
        
    Returns:
        Provider network status
    """
    provider = db.query(Provider).filter(Provider.npi == provider_npi).first()
    
    if not provider:
        return {
            "found": False,
            "message": "Provider not found in database",
        }
    
    return {
        "found": True,
        "name": provider.name,
        "npi": provider.npi,
        "network_status": provider.network_status.value,
        "is_in_network": provider.network_status.value != "out_of_network",
        "specialties": provider.specialties,
    }


# Export tools for use in graphs
POLICY_TOOLS = [get_policy_details, get_claim_status]
INCIDENT_TOOLS = [calculate_incident_claim_payout]
MEDICAL_TOOLS = [calculate_medical_claim_payout, check_provider_network]
ALL_TOOLS = POLICY_TOOLS + INCIDENT_TOOLS + MEDICAL_TOOLS
