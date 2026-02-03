"""
Policy Validation Service
Validates user eligibility for filing claims based on policy status and coverage.
"""
from typing import Optional, List
from dataclasses import dataclass
from datetime import date
from sqlalchemy.orm import Session

from app.db.models import Policy, PolicyCoverage, PolicyStatus, ProductType
from app.core.logging import logger


@dataclass
class PolicyValidationResult:
    """Result of policy validation check."""
    is_eligible: bool
    reason: str
    policy: Optional[Policy] = None
    coverages: List[PolicyCoverage] = None
    
    def __post_init__(self):
        if self.coverages is None:
            self.coverages = []


class PolicyValidationService:
    """Service for validating policy eligibility for claims."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_claim_eligibility(
        self,
        user_id: str,
        product_type: str,
    ) -> PolicyValidationResult:
        """
        Validate if user can file a claim for given product type.
        
        Checks:
        1. Policy exists for user and product type
        2. Policy status is ACTIVE
        3. Today is within coverage period
        
        Args:
            user_id: User's UUID
            product_type: "auto", "home", or "medical"
            
        Returns:
            PolicyValidationResult with eligibility status
        """
        # Map string to enum
        try:
            product_enum = ProductType(product_type)
        except ValueError:
            return PolicyValidationResult(
                is_eligible=False,
                reason=f"Invalid product type: {product_type}. Must be auto, home, or medical."
            )
        
        # Find user's policy for this product type
        policy = self.db.query(Policy).filter(
            Policy.user_id == user_id,
            Policy.product_type == product_enum,
        ).first()
        
        if not policy:
            logger.info(f"No policy found for user {user_id}, product {product_type}")
            return PolicyValidationResult(
                is_eligible=False,
                reason=f"No {product_type} policy found on your account. Would you like help getting a quote?"
            )
        
        # Check policy status
        if policy.status != PolicyStatus.ACTIVE:
            logger.info(f"Policy {policy.policy_number} is not active: {policy.status}")
            if policy.status == PolicyStatus.CANCELLED:
                return PolicyValidationResult(
                    is_eligible=False,
                    reason=f"Your {product_type} policy ({policy.policy_number}) has been cancelled. Please contact us to reinstate.",
                    policy=policy
                )
            elif policy.status == PolicyStatus.EXPIRED:
                return PolicyValidationResult(
                    is_eligible=False,
                    reason=f"Your {product_type} policy expired on {policy.expiration_date}. Please contact us to renew.",
                    policy=policy
                )
        
        # Check coverage period
        today = date.today()
        if today < policy.effective_date:
            return PolicyValidationResult(
                is_eligible=False,
                reason=f"Your policy becomes active on {policy.effective_date}. Please check back then.",
                policy=policy
            )
        
        if today > policy.expiration_date:
            return PolicyValidationResult(
                is_eligible=False,
                reason=f"Your policy expired on {policy.expiration_date}. Please contact us to renew.",
                policy=policy
            )
        
        # Get coverages
        coverages = list(policy.coverages)
        if not coverages:
            logger.warning(f"Policy {policy.policy_number} has no coverages defined")
            return PolicyValidationResult(
                is_eligible=False,
                reason="Your policy coverage details are missing. Please contact us for assistance.",
                policy=policy
            )
        
        logger.info(f"Policy {policy.policy_number} validated successfully for claim")
        return PolicyValidationResult(
            is_eligible=True,
            reason="Policy is active and within coverage period.",
            policy=policy,
            coverages=coverages
        )
    
    def get_coverage_for_claim(
        self,
        policy: Policy,
        coverage_type: str,
    ) -> Optional[PolicyCoverage]:
        """Get specific coverage from policy."""
        if not coverage_type:
            return None
        for coverage in policy.coverages:
            if coverage.coverage_type and coverage.coverage_type.lower() == coverage_type.lower():
                return coverage
        return None
    
    def get_primary_coverage(self, policy: Policy) -> Optional[PolicyCoverage]:
        """Get the primary coverage for a policy (highest limit)."""
        if not policy.coverages:
            return None
        return max(policy.coverages, key=lambda c: c.limit_amount)


def get_policy_validation_service(db: Session) -> PolicyValidationService:
    """Factory function for PolicyValidationService."""
    return PolicyValidationService(db)
