"""
Authentication API routes
"""
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import User, AuthLevel, UserRole
from app.core import hash_password, verify_password, create_access_token, logger

router = APIRouter()


# Request/Response schemas
class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
    policy_id: Optional[str] = None  # Policy ID if looked up during guest session


class UserResponse(BaseModel):
    user_id: str
    email: str
    name: str
    role: str
    auth_level: str


@router.post("/signup", response_model=TokenResponse)
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Register a new user."""
    # Check if email exists
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Create user
    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        name=request.name,
        auth_level=AuthLevel.AUTH,
        role=UserRole.CUSTOMER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create token
    token = create_access_token({
        "sub": str(user.user_id),
        "email": user.email,
        "role": user.role.value,
    })
    
    logger.info(f"User registered: {user.email}")
    
    return TokenResponse(
        access_token=token,
        user_id=str(user.user_id),
        role=user.role.value,
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return token."""
    user = db.query(User).filter(User.email == request.email).first()
    
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Create token
    token = create_access_token({
        "sub": str(user.user_id),
        "email": user.email,
        "role": user.role.value,
    })
    
    logger.info(f"User logged in: {user.email}")
    
    return TokenResponse(
        access_token=token,
        user_id=str(user.user_id),
        role=user.role.value,
    )


@router.post("/logout")
async def logout():
    """Logout user (client-side token invalidation)."""
    # In a stateless JWT setup, logout is handled client-side
    # For enhanced security, implement token blacklist with Redis
    return {"message": "Logged out successfully"}


@router.post("/guest-session", response_model=TokenResponse)
async def create_guest_session(
    name: str,
    email: EmailStr,
    policy_number: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Create a guest session for unauthenticated users."""
    from app.db.models import Policy

    # Check if email exists as authenticated user
    existing = db.query(User).filter(User.email == email).first()
    if existing and existing.auth_level == AuthLevel.AUTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered. Please login.",
        )

    # Create or update guest user
    if existing:
        user = existing
    else:
        user = User(
            email=email,
            password_hash="",  # Guest users don't have passwords
            name=name,
            auth_level=AuthLevel.GUEST,
            role=UserRole.CUSTOMER,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Lookup policy if policy_number provided
    policy_id = None
    if policy_number:
        policy = db.query(Policy).filter(Policy.policy_number == policy_number).first()
        if policy:
            policy_id = str(policy.policy_id)
            logger.info(f"Guest session with policy lookup: {policy_number} -> {policy_id}")

    # Create token with limited expiration
    token = create_access_token(
        {
            "sub": str(user.user_id),
            "email": user.email,
            "role": user.role.value,
            "auth_level": "guest",
        },
        expires_delta=timedelta(hours=2),
    )

    logger.info(f"Guest session created: {user.email}")

    return TokenResponse(
        access_token=token,
        user_id=str(user.user_id),
        role=user.role.value,
        policy_id=policy_id,
    )
