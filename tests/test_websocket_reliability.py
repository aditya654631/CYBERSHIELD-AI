import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.app.websocket.manager import ConnectionManager, ConnectionInfo


def test_dead_socket_pruned_on_broadcast_failure():
    async def run_test():
        manager = ConnectionManager()

        # Create one healthy mock socket and one failing mock socket
        good_socket = AsyncMock()
        bad_socket = AsyncMock()
        bad_socket.send_text.side_effect = RuntimeError("Socket broken pipe")

        class FakeUser:
            id = 1
            role = "I4C_ADMIN"
            state = "Delhi"
            district = "CENTRAL_NEW_DELHI"

        await manager.connect(good_socket, user=FakeUser())
        await manager.connect(bad_socket, user=FakeUser())

        assert len(manager.active_connections) == 2

        # Broadcast a message
        await manager.broadcast({"event": "TEST_ALERT", "message": "ping"})

        # Assert good socket received message
        good_socket.send_text.assert_called_once()
        # Bad socket was called and failed
        bad_socket.send_text.assert_called_once()

        # Bad socket should be automatically pruned
        assert len(manager.active_connections) == 1
        assert good_socket in manager.active_connections
        assert bad_socket not in manager.active_connections

    asyncio.run(run_test())


def test_jurisdiction_filtered_broadcast():
    async def run_test():
        manager = ConnectionManager()

        delhi_officer_socket = AsyncMock()
        mumbai_officer_socket = AsyncMock()
        i4c_admin_socket = AsyncMock()

        class DelhiUser:
            id = 10
            role = "STATE_LEA"
            state = "Delhi"
            district = "CENTRAL_NEW_DELHI"

        class MumbaiUser:
            id = 20
            role = "STATE_LEA"
            state = "Maharashtra"
            district = "MUMBAI_CITY"

        class I4CAdminUser:
            id = 30
            role = "I4C_ADMIN"
            state = "National"
            district = "ALL"

        await manager.connect(delhi_officer_socket, user=DelhiUser())
        await manager.connect(mumbai_officer_socket, user=MumbaiUser())
        await manager.connect(i4c_admin_socket, user=I4CAdminUser())

        # Broadcast event specifically targeted at Delhi
        delhi_alert = {
            "event": "NEW_ALERT",
            "state": "Delhi",
            "district": "CENTRAL_NEW_DELHI",
            "title": "Delhi High Value Fraud"
        }

        await manager.broadcast(delhi_alert)

        delhi_officer_socket.send_text.assert_called_once()
        i4c_admin_socket.send_text.assert_called_once()
        mumbai_officer_socket.send_text.assert_not_called()

    asyncio.run(run_test())


def test_graceful_close_all():
    async def run_test():
        manager = ConnectionManager()

        sock1 = AsyncMock()
        sock2 = AsyncMock()

        await manager.connect(sock1)
        await manager.connect(sock2)

        assert len(manager.active_connections) == 2

        await manager.close_all(code=1001, reason="Server shutting down")

        sock1.close.assert_called_once_with(code=1001, reason="Server shutting down")
        sock2.close.assert_called_once_with(code=1001, reason="Server shutting down")
        assert len(manager.active_connections) == 0

    asyncio.run(run_test())
