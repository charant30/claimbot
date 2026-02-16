"""
Tests for the calculation engine.
"""

import pytest
from decimal import Decimal
from app.services.calculation.engine import (
    calculate_incident_payout,
)


class TestIncidentCalculation:
    """Test auto incident claim calculations."""
    
    def test_basic_payout_calculation(self):
        """Test basic payout with deductible."""
        result = calculate_incident_payout(
            loss_amount=Decimal("10000.00"),
            deductible=Decimal("500.00"),
            coverage_limit=Decimal("50000.00"),
            exclusions=[],
            incident_type="collision",
        )
        assert float(result.payout_amount) == 9500.00
        assert float(result.deductible_applied) == 500.00
        assert result.is_total_loss is False
    
    def test_payout_exceeds_coverage_limit(self):
        """Test payout capped at coverage limit."""
        result = calculate_incident_payout(
            loss_amount=Decimal("100000.00"),
            deductible=Decimal("500.00"),
            coverage_limit=Decimal("50000.00"),
            exclusions=[],
            incident_type="collision",
        )
        # payout = min(99500, 50000) = 50000 (limit - 0 deductible applied to limit)
        # after_deductible = 99500, min(99500, 50000) = 50000
        assert float(result.payout_amount) == 50000.00
        assert float(result.coverage_limit) == 50000.00
    
    def test_total_loss_flag(self):
        """Test total loss flag when payout >= 75% of coverage limit."""
        result = calculate_incident_payout(
            loss_amount=Decimal("50000.00"),
            deductible=Decimal("500.00"),
            coverage_limit=Decimal("50000.00"),
            exclusions=[],
            incident_type="collision",
        )
        # payout = 49500, threshold = 37500, so is_total_loss True
        assert result.is_total_loss is True
        assert float(result.payout_amount) == 49500.00
    
    def test_claim_below_deductible(self):
        """Test claim amount below deductible."""
        result = calculate_incident_payout(
            loss_amount=Decimal("300.00"),
            deductible=Decimal("500.00"),
            coverage_limit=Decimal("50000.00"),
            exclusions=[],
            incident_type="collision",
        )
        assert float(result.payout_amount) == 0.00
        assert float(result.deductible_applied) == 300.00


class TestCalculationEdgeCases:
    """Test edge cases in calculations."""
    
    def test_zero_claim_amount(self):
        """Test handling of zero claim amount."""
        result = calculate_incident_payout(
            loss_amount=Decimal("0.00"),
            deductible=Decimal("500.00"),
            coverage_limit=Decimal("50000.00"),
            exclusions=[],
            incident_type="collision",
        )
        assert float(result.payout_amount) == 0.00
    
    def test_negative_deductible_raises(self):
        """Test that negative deductible raises ValueError."""
        with pytest.raises(ValueError, match="deductible cannot be negative"):
            calculate_incident_payout(
                loss_amount=Decimal("10000.00"),
                deductible=Decimal("-100.00"),
                coverage_limit=Decimal("50000.00"),
                exclusions=[],
                incident_type="collision",
            )
    
    def test_exclusion_zero_payout(self):
        """Test that matching exclusion results in zero payout."""
        result = calculate_incident_payout(
            loss_amount=Decimal("10000.00"),
            deductible=Decimal("500.00"),
            coverage_limit=Decimal("50000.00"),
            exclusions=["flood"],
            incident_type="comprehensive",
            incident_details={"description": "Vehicle damaged in flood"},
        )
        assert float(result.payout_amount) == 0.00
        assert "flood" in result.exclusions_applied
