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
    Calculate payout for auto incident claims.

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


