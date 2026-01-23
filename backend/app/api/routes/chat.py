"""
Chat API routes
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
import uuid as uuid_lib
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.models import Policy
from app.core import get_current_user_id, logger
from app.services.session_store import get_session_store

router = APIRouter()


# Request/Response schemas
class ChatSessionRequest(BaseModel):
    policy_id: Optional[str] = None


class ChatSessionResponse(BaseModel):
    thread_id: str
    policy_id: Optional[str]
    user_id: str
    created_at: str


class ChatMessageRequest(BaseModel):
    thread_id: str
    message: str
    metadata: Dict[str, Any] = {}


class ChatMessageResponse(BaseModel):
    message_id: str
    thread_id: str
    role: str  # "user" or "assistant"
    content: str
    metadata: Dict[str, Any] = {}


@router.post("/session", response_model=ChatSessionResponse)
async def create_chat_session(
    request: ChatSessionRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create a new chat session."""
    session_store = get_session_store()
    thread_id = str(uuid_lib.uuid4())

    # Validate policy if provided
    policy_id = None
    if request.policy_id:
        policy = db.query(Policy).filter(
            Policy.policy_id == request.policy_id,
            Policy.user_id == user_id,
        ).first()
        if policy:
            policy_id = str(policy.policy_id)

    session = {
        "thread_id": thread_id,
        "user_id": user_id,
        "policy_id": policy_id,
        "messages": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    session_store.set(thread_id, session, ttl_hours=24)

    logger.info(f"Chat session created: {thread_id}")

    return ChatSessionResponse(
        thread_id=thread_id,
        policy_id=policy_id,
        user_id=user_id,
        created_at=session["created_at"],
    )


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Send a message to the AI chatbot."""
    session_store = get_session_store()
    session = session_store.get(request.thread_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this session",
        )

    # Store user message
    user_msg = {
        "message_id": str(uuid_lib.uuid4()),
        "role": "user",
        "content": request.message,
        "metadata": request.metadata,
    }
    session["messages"].append(user_msg)

    # Process through LangGraph
    from app.services.chat import get_chat_service
    chat_service = get_chat_service(db)

    result = chat_service.process_message(
        thread_id=request.thread_id,
        user_id=user_id,
        message=request.message,
        policy_id=session.get("policy_id"),
    )

    assistant_msg = {
        "message_id": str(uuid_lib.uuid4()),
        "role": "assistant",
        "content": result.get("response", "I couldn't process that."),
        "metadata": {
            "intent": result.get("intent"),
            "product_line": result.get("product_line"),
            "should_escalate": result.get("should_escalate", False),
        },
    }
    session["messages"].append(assistant_msg)

    # Update session in store
    session_store.set(request.thread_id, session, ttl_hours=24)

    logger.info(f"Chat message in thread {request.thread_id}")

    return ChatMessageResponse(
        message_id=assistant_msg["message_id"],
        thread_id=request.thread_id,
        role="assistant",
        content=assistant_msg["content"],
        metadata=assistant_msg["metadata"],
    )


@router.get("/session/{thread_id}/messages", response_model=List[ChatMessageResponse])
async def get_session_messages(
    thread_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get all messages in a chat session."""
    session_store = get_session_store()
    session = session_store.get(thread_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    if session["user_id"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this session",
        )

    return [
        ChatMessageResponse(
            message_id=msg["message_id"],
            thread_id=thread_id,
            role=msg["role"],
            content=msg["content"],
            metadata=msg.get("metadata", {}),
        )
        for msg in session["messages"]
    ]
