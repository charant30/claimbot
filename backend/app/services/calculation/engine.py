"""
Deterministic Calculation Engine
All financial and coverage-related calculations are handled here, NOT by LLM.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import NamedTuple, List, Optional
from dataclasses import dataclass


@dataclass
class IncidentPayoutResult:
    """Result of incident claim payout calculation."""
    loss_amount: Decimal
    deductible_applied: Decimal
    coverage_limit: Decimal
    payout_amount: Decimal
    exclusions_applied: List[str]
    is_total_loss: bool
    breakdown: dict


@dataclass
class MedicalAdjudicationResult:
    """Result of medical claim adjudication."""
    billed_amount: Decimal
    allowed_amount: Decimal
    copay: Decimal
    deductible_applied: Decimal
    coinsurance_amount: Decimal
    member_responsibility: Decimal
    payer_responsibility: Decimal
    is_in_network: bool
    breakdown: dict


def round_currency(amount: Decimal) -> Decimal:
    """Round to 2 decimal places for currency."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_incident_payout(
    loss_amount: Decimal,
    deductible: Decimal,
    coverage_limit: Decimal,
    exclusions: List[str],
    incident_type: str,
    incident_details: dict = None,
) -> IncidentPayoutResult:
    """
    Calculate payout for incident claims (auto/home).

    Deterministic formula:
    payout = min(loss_amount - deductible, coverage_limit)

    Args:
        loss_amount: Total claimed loss amount
        deductible: Policy deductible to apply
        coverage_limit: Maximum coverage limit
        exclusions: List of coverage exclusions
        incident_type: Type of incident (collision, comprehensive, fire, water, etc.)
        incident_details: Additional incident metadata

    Returns:
        IncidentPayoutResult with breakdown

    Raises:
        ValueError: If loss_amount or deductible is negative
    """
    # Input validation
    if loss_amount < 0:
        raise ValueError("loss_amount cannot be negative")
    if deductible < 0:
        raise ValueError("deductible cannot be negative")
    if coverage_limit < 0:
        raise ValueError("coverage_limit cannot be negative")

    # Check for exclusions - use word boundary matching to avoid false positives
    exclusions_applied = []
    if incident_details:
        details_str = str(incident_details).lower()
        for excl in exclusions:
            excl_lower = excl.lower()
            # Match exact exclusion term or as part of a word boundary
            # Avoid "water damage" matching "waterfront property"
            import re
            if re.search(rf'\b{re.escape(excl_lower)}\b', details_str):
                exclusions_applied.append(excl)
    
    # If any exclusion applies, payout is zero
    if exclusions_applied:
        return IncidentPayoutResult(
            loss_amount=round_currency(loss_amount),
            deductible_applied=Decimal("0"),
            coverage_limit=round_currency(coverage_limit),
            payout_amount=Decimal("0"),
            exclusions_applied=exclusions_applied,
            is_total_loss=False,
            breakdown={
                "reason": "Claim denied due to exclusions",
                "exclusions": exclusions_applied,
            },
        )
    
    # Apply deductible
    after_deductible = max(loss_amount - deductible, Decimal("0"))
    
    # Apply coverage limit
    payout = min(after_deductible, coverage_limit)
    
    # Check for total loss (payout >= 75% of coverage limit for auto)
    total_loss_threshold = coverage_limit * Decimal("0.75")
    incident_type_lower = incident_type.lower() if incident_type else ""
    is_total_loss = payout >= total_loss_threshold and incident_type_lower in ["collision", "comprehensive"]
    
    return IncidentPayoutResult(
        loss_amount=round_currency(loss_amount),
        deductible_applied=round_currency(min(deductible, loss_amount)),
        coverage_limit=round_currency(coverage_limit),
        payout_amount=round_currency(payout),
        exclusions_applied=exclusions_applied,
        is_total_loss=is_total_loss,
        breakdown={
            "loss_amount": float(loss_amount),
            "deductible": float(deductible),
            "after_deductible": float(after_deductible),
            "coverage_limit": float(coverage_limit),
            "final_payout": float(payout),
            "is_total_loss": is_total_loss,
        },
    )


def adjudicate_medical_claim(
    billed_amount: Decimal,
    allowed_amount: Decimal,
    copay: Decimal,
    deductible_remaining: Decimal,
    coinsurance_pct: Decimal,
    coverage_limit: Decimal,
    is_in_network: bool,
) -> MedicalAdjudicationResult:
    """
    Adjudicate a medical claim with deterministic calculation.

    Order of operations:
    1. Start with allowed amount (network rate) or billed amount
    2. Subtract copay (member pays flat amount)
    3. Apply remaining deductible
    4. Apply coinsurance to remainder
    5. Check coverage limit

    Args:
        billed_amount: Amount billed by provider
        allowed_amount: Network-negotiated allowed amount (0 if out-of-network)
        copay: Flat copay amount
        deductible_remaining: Remaining deductible for the year
        coinsurance_pct: Member coinsurance percentage (e.g., 20 for 20%)
        coverage_limit: Plan coverage limit
        is_in_network: Whether provider is in-network

    Returns:
        MedicalAdjudicationResult with breakdown

    Raises:
        ValueError: If any amount is negative
    """
    # Input validation
    if billed_amount < 0:
        raise ValueError("billed_amount cannot be negative")
    if allowed_amount < 0:
        raise ValueError("allowed_amount cannot be negative")
    if copay < 0:
        raise ValueError("copay cannot be negative")
    if deductible_remaining < 0:
        raise ValueError("deductible_remaining cannot be negative")
    if coinsurance_pct < 0 or coinsurance_pct > 100:
        raise ValueError("coinsurance_pct must be between 0 and 100")
    if coverage_limit < 0:
        raise ValueError("coverage_limit cannot be negative")

    # Use allowed amount for in-network, billed for out-of-network
    base_amount = allowed_amount if is_in_network and allowed_amount > 0 else billed_amount

    # Out-of-network penalty: add 20% to coinsurance, with max of 60% (not 50%)
    # This ensures the full penalty is applied even for high base coinsurance
    effective_coinsurance = coinsurance_pct
    if not is_in_network:
        effective_coinsurance = min(coinsurance_pct + Decimal("20"), Decimal("60"))
    
    remaining = base_amount
    
    # 1. Apply copay
    copay_applied = min(copay, remaining)
    remaining = remaining - copay_applied
    
    # 2. Apply deductible
    deductible_applied = min(deductible_remaining, remaining)
    remaining = remaining - deductible_applied
    
    # 3. Apply coinsurance
    coinsurance_amount = round_currency(remaining * (effective_coinsurance / Decimal("100")))
    payer_pays_after_coinsurance = remaining - coinsurance_amount
    
    # 4. Check coverage limit
    payer_responsibility = min(payer_pays_after_coinsurance, coverage_limit)
    
    # Calculate member responsibility
    member_responsibility = copay_applied + deductible_applied + coinsurance_amount
    
    # If payer hit limit, member pays the rest
    if payer_pays_after_coinsurance > coverage_limit:
        excess = payer_pays_after_coinsurance - coverage_limit
        member_responsibility = member_responsibility + excess
    
    return MedicalAdjudicationResult(
        billed_amount=round_currency(billed_amount),
        allowed_amount=round_currency(allowed_amount),
        copay=round_currency(copay_applied),
        deductible_applied=round_currency(deductible_applied),
        coinsurance_amount=round_currency(coinsurance_amount),
        member_responsibility=round_currency(member_responsibility),
        payer_responsibility=round_currency(payer_responsibility),
        is_in_network=is_in_network,
        breakdown={
            "billed_amount": float(billed_amount),
            "allowed_amount": float(allowed_amount),
            "base_amount_used": float(base_amount),
            "copay": float(copay_applied),
            "deductible_applied": float(deductible_applied),
            "deductible_remaining_after": float(max(deductible_remaining - deductible_applied, 0)),
            "coinsurance_pct": float(effective_coinsurance),
            "coinsurance_amount": float(coinsurance_amount),
            "member_responsibility": float(member_responsibility),
            "payer_responsibility": float(payer_responsibility),
            "is_in_network": is_in_network,
        },
    )
