"""
WebSocket Manager for real-time session monitoring.

Provides broadcasting capabilities for admin live monitoring of chat sessions.
"""
import asyncio
from typing import Dict, Set, Any, Optional
from datetime import datetime
from fastapi import WebSocket
from app.core.logging import logger


class ConnectionManager:
    """
    Manages WebSocket connections for real-time monitoring.

    Supports multiple channels:
    - 'sessions': All active session updates
    - 'session:{thread_id}': Updates for a specific session
    - 'alerts': System alerts and escalations
    """

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.connection_info: Dict[WebSocket, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, channel: str = "sessions", user_id: Optional[str] = None):
        """Accept and register a WebSocket connection to a channel."""
        await websocket.accept()

        async with self._lock:
            if channel not in self.active_connections:
                self.active_connections[channel] = set()
            self.active_connections[channel].add(websocket)

            self.connection_info[websocket] = {
                "channel": channel,
                "user_id": user_id,
                "connected_at": datetime.utcnow().isoformat(),
            }

        logger.info(f"WebSocket connected to channel '{channel}' (user: {user_id})")

        await websocket.send_json({
            "type": "connected",
            "channel": channel,
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        async with self._lock:
            info = self.connection_info.pop(websocket, {})
            channel = info.get("channel", "sessions")

            if channel in self.active_connections:
                self.active_connections[channel].discard(websocket)
                if not self.active_connections[channel]:
                    del self.active_connections[channel]

        logger.info(f"WebSocket disconnected from channel '{channel}'")

    async def broadcast_to_channel(self, channel: str, message: Dict[str, Any]):
        """Broadcast a message to all connections in a channel."""
        if channel not in self.active_connections:
            return

        if "timestamp" not in message:
            message["timestamp"] = datetime.utcnow().isoformat()

        disconnected = set()

        for connection in self.active_connections[channel].copy():
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                disconnected.add(connection)

        for conn in disconnected:
            await self.disconnect(conn)

    async def broadcast_session_update(
        self,
        thread_id: str,
        event_type: str,
        data: Dict[str, Any],
    ):
        """Broadcast a session update to relevant channels."""
        message = {
            "type": "session_update",
            "event": event_type,
            "thread_id": thread_id,
            "data": data,
        }

        await self.broadcast_to_channel("sessions", message)
        await self.broadcast_to_channel(f"session:{thread_id}", message)

        if event_type == "escalation":
            await self.broadcast_to_channel("alerts", {
                "type": "alert",
                "alert_type": "escalation",
                "thread_id": thread_id,
                "data": data,
            })

    async def broadcast_new_session(self, session_data: Dict[str, Any]):
        """Broadcast when a new session is created."""
        await self.broadcast_to_channel("sessions", {
            "type": "new_session",
            "data": session_data,
        })

    async def broadcast_session_ended(self, thread_id: str, summary: Dict[str, Any]):
        """Broadcast when a session ends."""
        await self.broadcast_to_channel("sessions", {
            "type": "session_ended",
            "thread_id": thread_id,
            "data": summary,
        })

    def get_channel_count(self, channel: str) -> int:
        """Get the number of connections in a channel."""
        return len(self.active_connections.get(channel, set()))

    def get_all_channel_counts(self) -> Dict[str, int]:
        """Get connection counts for all channels."""
        return {
            channel: len(connections)
            for channel, connections in self.active_connections.items()
        }


# Global instance
_manager: Optional[ConnectionManager] = None


def get_websocket_manager() -> ConnectionManager:
    """Get or create the global WebSocket manager."""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager


async def broadcast_session_event(
    thread_id: str,
    event_type: str,
    data: Dict[str, Any],
):
    """Broadcast a session event to monitoring clients."""
    manager = get_websocket_manager()
    await manager.broadcast_session_update(thread_id, event_type, data)


async def broadcast_message(
    thread_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
):
    """Broadcast a new message in a session."""
    await broadcast_session_event(thread_id, "message", {
        "role": role,
        "content": content[:500] if len(content) > 500 else content,
        "metadata": metadata or {},
    })


async def broadcast_state_change(
    thread_id: str,
    old_state: str,
    new_state: str,
    details: Optional[Dict[str, Any]] = None,
):
    """Broadcast a state change in a session."""
    await broadcast_session_event(thread_id, "state_change", {
        "old_state": old_state,
        "new_state": new_state,
        "details": details or {},
    })


async def broadcast_escalation(
    thread_id: str,
    reason: str,
    case_packet: Dict[str, Any],
):
    """Broadcast an escalation event."""
    await broadcast_session_event(thread_id, "escalation", {
        "reason": reason,
        "case_packet": case_packet,
    })