"""
Tests for the calculation engine.
"""

import pytest
from app.services.calculation.engine import (
    calculate_incident_payout,
    calculate_medical_claim,
)


class TestIncidentCalculation:
    """Test incident (auto/home) claim calculations."""
    
    def test_basic_payout_calculation(self):
        """Test basic payout with deductible."""
        result = calculate_incident_payout(
            claim_amount=10000.00,
            deductible=500.00,
            coverage_limit=50000.00,
        )
        assert result["payout_amount"] == 9500.00
        assert result["deductible_applied"] == 500.00
        assert result["is_total_loss"] is False
    
    def test_payout_exceeds_coverage_limit(self):
        """Test payout capped at coverage limit."""
        result = calculate_incident_payout(
            claim_amount=100000.00,
            deductible=500.00,
            coverage_limit=50000.00,
        )
        assert result["payout_amount"] == 49500.00  # limit - deductible
        assert result["coverage_limit_applied"] is True
    
    def test_total_loss_calculation(self):
        """Test total loss flag with depreciation."""
        result = calculate_incident_payout(
            claim_amount=25000.00,
            deductible=500.00,
            coverage_limit=50000.00,
            is_total_loss=True,
            vehicle_value=20000.00,
            depreciation_rate=0.10,
        )
        # Total loss: vehicle value - depreciation - deductible
        assert result["is_total_loss"] is True
        assert result["payout_amount"] == 17500.00  # 20000 * 0.9 - 500
    
    def test_claim_below_deductible(self):
        """Test claim amount below deductible."""
        result = calculate_incident_payout(
            claim_amount=300.00,
            deductible=500.00,
            coverage_limit=50000.00,
        )
        assert result["payout_amount"] == 0.00
        assert result["reason"] == "Claim amount is below deductible"


class TestMedicalCalculation:
    """Test medical claim adjudication calculations."""
    
    def test_in_network_calculation(self):
        """Test in-network provider calculation."""
        result = calculate_medical_claim(
            billed_amount=1000.00,
            allowed_amount=800.00,
            is_in_network=True,
            coinsurance_rate=0.20,
            copay=25.00,
            deductible_remaining=0.00,
        )
        # Patient pays: copay + (allowed * coinsurance) = 25 + (800 * 0.20) = 185
        # Plan pays: allowed - patient responsibility = 800 - 185 = 615
        assert result["plan_pays"] == 615.00
        assert result["patient_pays"] == 185.00
    
    def test_out_of_network_calculation(self):
        """Test out-of-network provider calculation."""
        result = calculate_medical_claim(
            billed_amount=1000.00,
            allowed_amount=500.00,  # Lower allowed amount for OON
            is_in_network=False,
            coinsurance_rate=0.40,  # Higher coinsurance for OON
            copay=50.00,  # Higher copay for OON
            deductible_remaining=0.00,
        )
        # Patient pays more for OON
        assert result["is_in_network"] is False
        assert result["patient_pays"] > result["plan_pays"]
    
    def test_deductible_applied(self):
        """Test deductible is applied before coinsurance."""
        result = calculate_medical_claim(
            billed_amount=500.00,
            allowed_amount=400.00,
            is_in_network=True,
            coinsurance_rate=0.20,
            copay=25.00,
            deductible_remaining=200.00,
        )
        # Deductible comes out first, then coinsurance on remainder
        assert result["deductible_applied"] == 200.00
    
    def test_out_of_pocket_max(self):
        """Test out-of-pocket maximum protection."""
        result = calculate_medical_claim(
            billed_amount=100000.00,
            allowed_amount=80000.00,
            is_in_network=True,
            coinsurance_rate=0.20,
            copay=25.00,
            deductible_remaining=0.00,
            oop_max=6000.00,
            oop_spent=5500.00,
        )
        # Should only pay up to remaining OOP max
        assert result["patient_pays"] <= 500.00  # 6000 - 5500


class TestCalculationEdgeCases:
    """Test edge cases in calculations."""
    
    def test_zero_claim_amount(self):
        """Test handling of zero claim amount."""
        result = calculate_incident_payout(
            claim_amount=0.00,
            deductible=500.00,
            coverage_limit=50000.00,
        )
        assert result["payout_amount"] == 0.00
    
    def test_negative_deductible_handled(self):
        """Test that negative deductible is treated as zero."""
        result = calculate_incident_payout(
            claim_amount=10000.00,
            deductible=-100.00,  # Invalid, should be treated as 0
            coverage_limit=50000.00,
        )
        assert result["deductible_applied"] == 0.00
        assert result["payout_amount"] == 10000.00
