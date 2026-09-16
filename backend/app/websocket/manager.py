import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import WebSocket

logger = logging.getLogger("cybershield.websocket")


class ConnectionInfo:
    def __init__(
        self,
        websocket: WebSocket,
        user_id: Optional[int] = None,
        role: Optional[str] = None,
        state: Optional[str] = None,
        district: Optional[str] = None,
    ):
        self.websocket = websocket
        self.user_id = user_id
        self.role = role.upper() if role else "ANALYST"
        self.state = state
        self.district = district
        self.connected_at = datetime.now(timezone.utc)


class ConnectionManager:
    def __init__(self):
        self._connections: List[ConnectionInfo] = []

    @property
    def active_connections(self) -> List[WebSocket]:
        """Backward-compatible list of raw WebSocket instances."""
        return [c.websocket for c in self._connections]

    async def connect(self, websocket: WebSocket, user: Optional[Any] = None):
        """Accepts a WebSocket connection and registers authenticated user context."""
        await websocket.accept()
        user_id = getattr(user, "id", None)
        role = getattr(user, "role", None)
        state = getattr(user, "state", None)
        district = getattr(user, "district", None)

        conn_info = ConnectionInfo(
            websocket=websocket,
            user_id=user_id,
            role=role,
            state=state,
            district=district,
        )
        self._connections.append(conn_info)
        logger.info(
            "WebSocket client connected: user_id=%s role=%s state=%s district=%s (total: %d)",
            user_id, role, state, district, len(self._connections)
        )

    def disconnect(self, websocket: WebSocket):
        """Removes a WebSocket connection from the registry."""
        initial_len = len(self._connections)
        self._connections = [c for c in self._connections if c.websocket != websocket]
        if len(self._connections) < initial_len:
            logger.info("WebSocket client disconnected (remaining: %d)", len(self._connections))

    def _should_deliver(
        self,
        conn: ConnectionInfo,
        target_state: Optional[str],
        target_district: Optional[str],
        required_roles: Optional[List[str]],
    ) -> bool:
        """Evaluates whether an event should be delivered to a connection based on jurisdiction & RBAC."""
        # 1. Role requirement check
        if required_roles:
            normalized_roles = [r.upper() for r in required_roles]
            if conn.role not in normalized_roles:
                return False

        # National / Auditor roles can see all events
        if conn.role in ("I4C_ADMIN", "ADMIN", "AUDITOR"):
            return True

        # 2. State jurisdiction check
        if target_state:
            conn_state = (conn.state or "").strip().lower()
            t_state = target_state.strip().lower()
            if conn_state != t_state:
                return False

        # 3. District jurisdiction check
        if target_district and conn.role in ("DISTRICT_LEA", "INVESTIGATOR"):
            conn_dist = (conn.district or "").strip().lower()
            t_dist = target_district.strip().lower()
            if conn_dist != t_dist:
                return False

        return True

    async def broadcast(
        self,
        message: Dict[str, Any],
        target_state: Optional[str] = None,
        target_district: Optional[str] = None,
        required_roles: Optional[List[str]] = None,
    ):
        """
        Broadcasts message to authorized connected clients with per-connection error isolation
        and immediate dead-socket pruning.
        """
        # If target jurisdiction is not explicitly provided, extract from message payload
        if not target_state:
            target_state = message.get("state") or message.get("complaint_state")
        if not target_district:
            target_district = message.get("district") or message.get("complaint_district")

        dead_connections: List[ConnectionInfo] = []
        payload = json.dumps(message)

        for conn in list(self._connections):
            if not self._should_deliver(conn, target_state, target_district, required_roles):
                continue

            try:
                await conn.websocket.send_text(payload)
            except Exception as exc:
                logger.warning("Error sending WebSocket message to user_id=%s: %s", conn.user_id, exc)
                dead_connections.append(conn)

        # Immediately prune dead connections
        for dead in dead_connections:
            self.disconnect(dead.websocket)

    async def close_all(self, code: int = 1001, reason: str = "Server shutdown"):
        """Gracefully closes all active connections with status code (1001: Going Away)."""
        logger.info("Closing all active WebSocket connections (%d)...", len(self._connections))
        for conn in list(self._connections):
            try:
                await conn.websocket.close(code=code, reason=reason)
            except Exception:
                pass
        self._connections.clear()


ws_manager = ConnectionManager()
