"""
Test configuration and fixtures for ClaimBot backend tests.
"""

import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from main import app
from app.db.base import Base
from app.db.session import get_db
from app.core.security import create_access_token, hash_password


# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db() -> Generator[Session, None, None]:
    """Override database dependency for tests."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database override."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db: Session):
    """Create a test user."""
    from app.db.models import User, UserRole, AuthLevel

    user = User(
        email="test@example.com",
        password_hash=hash_password("testpass123"),
        name="Test User",
        role=UserRole.CUSTOMER,
        auth_level=AuthLevel.AUTH,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_admin(db: Session):
    """Create a test admin user."""
    from app.db.models import User, UserRole, AuthLevel

    admin = User(
        email="admin@example.com",
        password_hash=hash_password("adminpass123"),
        name="Test Admin",
        role=UserRole.ADMIN,
        auth_level=AuthLevel.AUTH,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@pytest.fixture
def test_celest(db: Session):
    """Create a test Celest agent."""
    from app.db.models import User, UserRole, AuthLevel

    celest = User(
        email="celest@example.com",
        password_hash=hash_password("celestpass123"),
        name="Test Agent",
        role=UserRole.CELEST,
        auth_level=AuthLevel.AUTH,
    )
    db.add(celest)
    db.commit()
    db.refresh(celest)
    return celest


@pytest.fixture
def user_token(test_user):
    """Get an access token for the test user."""
    return create_access_token(
        data={"sub": str(test_user.user_id), "role": test_user.role.value}
    )


@pytest.fixture
def admin_token(test_admin):
    """Get an access token for the test admin."""
    return create_access_token(
        data={"sub": str(test_admin.user_id), "role": test_admin.role.value}
    )


@pytest.fixture
def celest_token(test_celest):
    """Get an access token for the test Celest agent."""
    return create_access_token(
        data={"sub": str(test_celest.user_id), "role": test_celest.role.value}
    )


@pytest.fixture
def auth_headers(user_token: str) -> dict:
    """Get authorization headers for the test user."""
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def admin_headers(admin_token: str) -> dict:
    """Get authorization headers for the test admin."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def celest_headers(celest_token: str) -> dict:
    """Get authorization headers for the test Celest agent."""
    return {"Authorization": f"Bearer {celest_token}"}


@pytest.fixture
def test_policy(db: Session, test_user):
    """Create a test policy."""
    from datetime import date
    from app.db.models import Policy, PolicyStatus

    policy = Policy(
        user_id=test_user.user_id,
        policy_number="TEST-2024-001234",
        product_type="auto",
        effective_date=date(2024, 1, 1),
        expiration_date=date(2025, 1, 1),
        status=PolicyStatus.ACTIVE,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@pytest.fixture
def test_claim(db: Session, test_policy):
    """Create a test claim."""
    from datetime import date
    from app.db.models import Claim, ClaimType, ClaimStatus

    claim = Claim(
        policy_id=test_policy.policy_id,
        claim_number="CLM-2024-TEST001",
        claim_type=ClaimType.INCIDENT,
        status=ClaimStatus.SUBMITTED,
        incident_date=date(2024, 1, 15),
        loss_amount=5000.00,
        claim_metadata={"description": "Test incident"},
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)
    return claim
