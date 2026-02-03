"""
WebSocket routes for real-time monitoring.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional

from app.services.websocket_manager import get_websocket_manager
from app.core.logging import logger

router = APIRouter()


@router.websocket("/monitor")
async def websocket_monitor(
    websocket: WebSocket,
    channel: str = Query(default="sessions"),
    token: Optional[str] = Query(default=None),
):
    """
    WebSocket endpoint for real-time session monitoring.

    Query params:
    - channel: Channel to subscribe to (sessions, alerts, session:{thread_id})
    - token: JWT token for authentication

    Message types received:
    - connected: Connection confirmation
    - new_session: New session created
    - session_update: Session state/message update
    - session_ended: Session completed
    - alert: System alert (escalation, error)
    """
    manager = get_websocket_manager()

    # Validate token (simplified - in production use proper JWT validation)
    user_id = None
    if token:
        try:
            from app.core.auth import decode_token
            payload = decode_token(token)
            user_id = payload.get("sub")
            role = payload.get("role")

            if role != "admin":
                await websocket.close(code=4003, reason="Admin access required")
                return
        except Exception as e:
            logger.warning(f"WebSocket auth failed: {e}")
            await websocket.close(code=4001, reason="Invalid token")
            return

    try:
        await manager.connect(websocket, channel, user_id)

        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_json()

            # Handle client commands
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif data.get("type") == "subscribe":
                # Allow subscribing to additional channels
                new_channel = data.get("channel")
                if new_channel:
                    await manager.connect(websocket, new_channel, user_id)
            elif data.get("type") == "unsubscribe":
                # Unsubscribe from a channel
                pass  # Could implement channel removal

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(websocket)


@router.get("/monitor/status")
async def get_monitor_status():
    """Get current WebSocket monitor status."""
    manager = get_websocket_manager()
    return {
        "channels": manager.get_all_channel_counts(),
        "total_connections": sum(manager.get_all_channel_counts().values()),
    }
