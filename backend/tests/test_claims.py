"""
Tests for claims API endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestClaimsEndpoints:
    """Test claims-related API endpoints."""
    
    def test_get_my_claims_empty(self, client: TestClient, auth_headers):
        """Test getting claims when user has none."""
        response = client.get("/claims/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_my_claims(self, client: TestClient, auth_headers, test_claim):
        """Test getting user's claims."""
        response = client.get("/claims/me", headers=auth_headers)
        assert response.status_code == 200
        claims = response.json()
        assert len(claims) == 1
        assert claims[0]["claim_number"] == test_claim.claim_number
    
    def test_get_claim_by_id(self, client: TestClient, auth_headers, test_claim):
        """Test getting a specific claim."""
        response = client.get(
            f"/claims/{test_claim.claim_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        claim = response.json()
        assert claim["claim_id"] == str(test_claim.claim_id)
        assert claim["status"] == "submitted"
    
    def test_get_claim_not_found(self, client: TestClient, auth_headers):
        """Test getting non-existent claim fails."""
        import uuid
        fake_id = str(uuid.uuid4())
        response = client.get(f"/claims/{fake_id}", headers=auth_headers)
        assert response.status_code == 404
    
    def test_get_claim_unauthorized(self, client: TestClient, test_claim):
        """Test getting claim without auth fails."""
        response = client.get(f"/claims/{test_claim.claim_id}")
        assert response.status_code == 401
    
    def test_create_claim(self, client: TestClient, auth_headers, test_policy):
        """Test creating a new claim."""
        response = client.post(
            "/claims/",
            headers=auth_headers,
            json={
                "policy_id": str(test_policy.policy_id),
                "claim_type": "incident",
                "incident_date": "2024-01-20",
                "incident_description": "Fender bender in parking lot",
                "loss_amount": 2500.00,
            }
        )
        assert response.status_code == 200
        claim = response.json()
        assert claim["status"] == "draft"
        assert claim["loss_amount"] == 2500.00
        assert "claim_number" in claim
    
    def test_update_claim(self, client: TestClient, auth_headers, test_claim):
        """Test updating a claim."""
        response = client.patch(
            f"/claims/{test_claim.claim_id}",
            headers=auth_headers,
            json={
                "incident_description": "Updated description with more details",
            }
        )
        assert response.status_code == 200
        claim = response.json()
        assert "Updated description" in claim["incident_description"]
    
    def test_submit_claim(self, client: TestClient, auth_headers, db, test_policy):
        """Test submitting a draft claim."""
        # First create a draft claim
        from app.db.models import Claim
        
        draft_claim = Claim(
            user_id=test_policy.user_id,
            policy_id=test_policy.policy_id,
            claim_number="CLM-2024-DRAFT01",
            claim_type="incident",
            incident_date="2024-01-20",
            incident_description="Test draft",
            status="draft",
            loss_amount=1000.00,
        )
        db.add(draft_claim)
        db.commit()
        db.refresh(draft_claim)
        
        # Submit it
        response = client.post(
            f"/claims/{draft_claim.claim_id}/submit",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "submitted"


class TestClaimsAuthorization:
    """Test claims authorization rules."""
    
    def test_cannot_access_other_user_claim(
        self, client: TestClient, auth_headers, db, test_admin
    ):
        """Test that users cannot access other users' claims."""
        # Create a claim for admin user
        from app.db.models import Policy, Claim
        
        admin_policy = Policy(
            user_id=test_admin.user_id,
            policy_number="ADMIN-2024-001",
            product_type="home",
            effective_date="2024-01-01",
            expiration_date="2025-01-01",
            status="active",
            is_active=True,
        )
        db.add(admin_policy)
        db.commit()
        db.refresh(admin_policy)
        
        admin_claim = Claim(
            user_id=test_admin.user_id,
            policy_id=admin_policy.policy_id,
            claim_number="CLM-2024-ADMIN01",
            claim_type="incident",
            incident_date="2024-01-15",
            incident_description="Admin's claim",
            status="submitted",
            loss_amount=10000.00,
        )
        db.add(admin_claim)
        db.commit()
        db.refresh(admin_claim)
        
        # Try to access with regular user (should fail)
        response = client.get(
            f"/claims/{admin_claim.claim_id}",
            headers=auth_headers  # Regular user token
        )
        assert response.status_code == 404  # Not found (not forbidden, for security)
