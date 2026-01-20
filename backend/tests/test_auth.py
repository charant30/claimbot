"""
Tests for authentication endpoints.
"""

import pytest
from fastapi.testclient import TestClient


class TestAuthEndpoints:
    """Test authentication-related API endpoints."""
    
    def test_signup_success(self, client: TestClient):
        """Test successful user registration."""
        response = client.post(
            "/auth/signup",
            json={
                "email": "newuser@example.com",
                "password": "securepass123",
                "name": "New User",
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["email"] == "newuser@example.com"
        assert data["role"] == "customer"
    
    def test_signup_duplicate_email(self, client: TestClient, test_user):
        """Test registration with existing email fails."""
        response = client.post(
            "/auth/signup",
            json={
                "email": "test@example.com",  # Already exists
                "password": "securepass123",
                "name": "Duplicate User",
            }
        )
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()
    
    def test_login_success(self, client: TestClient, test_user):
        """Test successful login."""
        response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "testpass123",
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user_id"] == str(test_user.user_id)
    
    def test_login_wrong_password(self, client: TestClient, test_user):
        """Test login with wrong password fails."""
        response = client.post(
            "/auth/login",
            json={
                "email": "test@example.com",
                "password": "wrongpassword",
            }
        )
        assert response.status_code == 401
    
    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with non-existent user fails."""
        response = client.post(
            "/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "anypassword",
            }
        )
        assert response.status_code == 401
    
    def test_guest_session(self, client: TestClient):
        """Test guest session creation."""
        response = client.post(
            "/auth/guest",
            json={
                "name": "Guest User",
                "email": "guest@example.com",
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["authentication_level"] == "guest"
    
    def test_me_endpoint(self, client: TestClient, auth_headers, test_user):
        """Test getting current user info."""
        response = client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["user_id"] == str(test_user.user_id)
    
    def test_me_endpoint_unauthorized(self, client: TestClient):
        """Test /me endpoint without auth fails."""
        response = client.get("/auth/me")
        assert response.status_code == 401


class TestAuthSecurity:
    """Test authentication security measures."""
    
    def test_password_not_in_response(self, client: TestClient):
        """Ensure password is never returned in responses."""
        response = client.post(
            "/auth/signup",
            json={
                "email": "sectest@example.com",
                "password": "securepass123",
                "name": "Security Test",
            }
        )
        data = response.json()
        assert "password" not in data
        assert "password_hash" not in data
    
    def test_invalid_token_rejected(self, client: TestClient):
        """Test that invalid tokens are rejected."""
        response = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        assert response.status_code == 401
    
    def test_expired_token_format(self, client: TestClient):
        """Test that malformed tokens are rejected."""
        response = client.get(
            "/auth/me",
            headers={"Authorization": "NotBearer token"}
        )
        assert response.status_code == 401
