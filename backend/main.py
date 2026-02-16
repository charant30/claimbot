"""
ClaimBot Backend - Main Application Entry Point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import auth, policies, claims, documents, chat, handoff, admin, websocket, fnol


def _ensure_admin_user():
    """In development, ensure an admin user exists so login works without manual seeding."""
    if settings.APP_ENV != "development":
        return
    try:
        from app.db.session import SessionLocal
        from app.db.models import User, AuthLevel, UserRole
        from app.core import hash_password
        db = SessionLocal()
        try:
            admin_user = db.query(User).filter(User.role == UserRole.ADMIN).first()
            if admin_user:
                return
            admin = User(
                email="admin@claimbot.demo",
                password_hash=hash_password("admin123"),
                name="System Admin",
                auth_level=AuthLevel.AUTH,
                role=UserRole.ADMIN,
            )
            db.add(admin)
            db.commit()
            print("  Created default admin user: admin@claimbot.demo / admin123")
        finally:
            db.close()
    except Exception as e:
        print(f"  Note: Could not ensure admin user (database may not be ready): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    # Startup
    print(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
    _ensure_admin_user()
    yield
    # Shutdown
    print("Shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Insurance Claims Automation Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://localhost:3001", "http://localhost:3002",
        "http://127.0.0.1:3000", "http://127.0.0.1:3001", "http://127.0.0.1:3002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(policies.router, prefix="/policies", tags=["Policies"])
app.include_router(claims.router, prefix="/claims", tags=["Claims"])
app.include_router(documents.router, prefix="/documents", tags=["Documents"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(handoff.router, prefix="/handoff", tags=["Handoff"])
app.include_router(admin.router, prefix="/admin", tags=["Admin"])
app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])
app.include_router(fnol.router, prefix="/fnol", tags=["FNOL"])


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
    }


@app.get("/me")
async def get_current_user():
    """Placeholder - will be implemented with auth dependency."""
    return {"message": "Requires authentication"}
