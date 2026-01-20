"""
Tests for admin API endpoints and role-based access control.
"""

import pytest
from fastapi.testclient import TestClient


class TestAdminAccess:
    """Test admin endpoint access control."""
    
    def test_admin_can_access_metrics(self, client: TestClient, admin_headers):
        """Test admin can access metrics endpoint."""
        response = client.get("/admin/metrics", headers=admin_headers)
        assert response.status_code == 200
    
    def test_customer_cannot_access_admin(self, client: TestClient, auth_headers):
        """Test customer cannot access admin endpoints."""
        response = client.get("/admin/metrics", headers=auth_headers)
        assert response.status_code == 403
    
    def test_unauthenticated_cannot_access_admin(self, client: TestClient):
        """Test unauthenticated users cannot access admin endpoints."""
        response = client.get("/admin/metrics")
        assert response.status_code == 401
    
    def test_admin_can_get_llm_settings(self, client: TestClient, admin_headers):
        """Test admin can retrieve LLM settings."""
        response = client.get("/admin/llm-settings", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "llm_provider" in data
    
    def test_admin_can_get_audit_logs(self, client: TestClient, admin_headers):
        """Test admin can access audit logs."""
        response = client.get("/admin/audit-logs", headers=admin_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestCelestAccess:
    """Test Celest agent endpoint access control."""
    
    def test_celest_can_access_queue(self, client: TestClient, celest_headers):
        """Test Celest agent can access escalation queue."""
        response = client.get("/handoff/queue", headers=celest_headers)
        assert response.status_code == 200
    
    def test_customer_cannot_access_queue(self, client: TestClient, auth_headers):
        """Test customer cannot access escalation queue."""
        response = client.get("/handoff/queue", headers=auth_headers)
        assert response.status_code == 403
    
    def test_admin_can_access_queue(self, client: TestClient, admin_headers):
        """Test admin can also access escalation queue."""
        response = client.get("/handoff/queue", headers=admin_headers)
        assert response.status_code == 200


class TestRoleBasedDataAccess:
    """Test role-based data access rules."""
    
    def test_customer_only_sees_own_policies(
        self, client: TestClient, auth_headers, test_policy
    ):
        """Test customer can only see their own policies."""
        response = client.get("/policies/me", headers=auth_headers)
        assert response.status_code == 200
        policies = response.json()
        # All returned policies should belong to the authenticated user
        for policy in policies:
            assert policy["policy_number"] == test_policy.policy_number
    
    def test_customer_only_sees_own_claims(
        self, client: TestClient, auth_headers, test_claim
    ):
        """Test customer can only see their own claims."""
        response = client.get("/claims/me", headers=auth_headers)
        assert response.status_code == 200
        claims = response.json()
        for claim in claims:
            assert claim["claim_number"] == test_claim.claim_number
