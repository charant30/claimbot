"""
ClaimBot Backend - Main Application Entry Point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import auth, policies, claims, documents, chat, handoff, admin, websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    # Startup
    print(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")
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
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
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
