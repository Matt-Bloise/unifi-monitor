# test_ws.py -- WebSocket ConnectionManager tests

from __future__ import annotations

import pytest

from unifi_monitor.ws import ConnectionManager


class FakeWebSocket:
    """Minimal mock for fastapi.WebSocket."""

    def __init__(self, *, fail_on_send: bool = False) -> None:
        self.accepted = False
        self.messages: list[dict] = []
        self._fail_on_send = fail_on_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: dict) -> None:
        if self._fail_on_send:
            raise RuntimeError("connection closed")
        self.messages.append(data)


@pytest.mark.asyncio
async def test_connect_disconnect() -> None:
    mgr = ConnectionManager()
    ws = FakeWebSocket()
    await mgr.connect(ws)
    assert ws.accepted
    assert len(mgr._connections) == 1
    mgr.disconnect(ws)
    assert len(mgr._connections) == 0


@pytest.mark.asyncio
async def test_broadcast_sends_to_all() -> None:
    mgr = ConnectionManager()
    ws1 = FakeWebSocket()
    ws2 = FakeWebSocket()
    await mgr.connect(ws1)
    await mgr.connect(ws2)
    await mgr.broadcast({"type": "update", "data": 1})
    assert len(ws1.messages) == 1
    assert len(ws2.messages) == 1
    assert ws1.messages[0]["type"] == "update"


@pytest.mark.asyncio
async def test_broadcast_skips_dead_connections() -> None:
    mgr = ConnectionManager()
    ws_ok = FakeWebSocket()
    ws_dead = FakeWebSocket(fail_on_send=True)
    await mgr.connect(ws_ok)
    await mgr.connect(ws_dead)
    assert len(mgr._connections) == 2
    await mgr.broadcast({"type": "update"})
    # Dead connection should be removed
    assert len(mgr._connections) == 1
    assert len(ws_ok.messages) == 1


@pytest.mark.asyncio
async def test_broadcast_empty_no_op() -> None:
    mgr = ConnectionManager()
    await mgr.broadcast({"type": "update"})  # Should not raise


@pytest.mark.asyncio
async def test_disconnect_idempotent() -> None:
    mgr = ConnectionManager()
    ws = FakeWebSocket()
    await mgr.connect(ws)
    mgr.disconnect(ws)
    mgr.disconnect(ws)  # Should not raise
    assert len(mgr._connections) == 0
