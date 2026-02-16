"""
Tests for claims API endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestClaimsEndpoints:
    """Test claims-related API endpoints."""
    
    def test_get_my_claims_empty(self, client: TestClient, auth_headers):
        """Test getting claims when user has none."""
        response = client.get("/claims/", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []
    
    def test_get_my_claims(self, client: TestClient, auth_headers, test_claim):
        """Test getting user's claims."""
        response = client.get("/claims/", headers=auth_headers)
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
                "metadata": {
                    "description": "Fender bender in parking lot",
                    "estimated_loss": 2500.00,
                },
            }
        )
        assert response.status_code == 200
        claim = response.json()
        assert claim["status"] == "draft"
        assert "claim_number" in claim
        assert claim["metadata"].get("description") == "Fender bender in parking lot"
    
    def test_update_claim(self, client: TestClient, auth_headers, test_claim):
        """Test updating a claim."""
        response = client.patch(
            f"/claims/{test_claim.claim_id}",
            headers=auth_headers,
            json={
                "metadata": {"description": "Updated description with more details"},
            }
        )
        assert response.status_code == 200
        claim = response.json()
        assert "Updated description" in (claim["metadata"] or {}).get("description", "")


class TestClaimsAuthorization:
    """Test claims authorization rules."""
    
    def test_cannot_access_other_user_claim(
        self, client: TestClient, auth_headers, db, test_admin
    ):
        """Test that users cannot access other users' claims."""
        from app.db.models import Policy, PolicyStatus, Claim, ClaimType, ClaimStatus
        
        admin_policy = Policy(
            user_id=test_admin.user_id,
            policy_number="ADMIN-2024-001",
            product_type="auto",
            effective_date="2024-01-01",
            expiration_date="2025-01-01",
            status=PolicyStatus.ACTIVE,
        )
        db.add(admin_policy)
        db.commit()
        db.refresh(admin_policy)
        
        admin_claim = Claim(
            policy_id=admin_policy.policy_id,
            claim_number="CLM-2024-ADMIN01",
            claim_type=ClaimType.INCIDENT,
            status=ClaimStatus.SUBMITTED,
            incident_date="2024-01-15",
            loss_amount=10000.00,
            claim_metadata={"description": "Admin's claim"},
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
