# ws.py -- WebSocket broadcast hub for live dashboard updates
# In-memory connection set. Single-process only (no Redis/pub-sub needed).

from __future__ import annotations

import logging

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

log = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts updates."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.add(ws)
        log.debug("WebSocket connected (%d total)", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.discard(ws)
        log.debug("WebSocket disconnected (%d total)", len(self._connections))

    async def broadcast(self, data: dict) -> None:
        if not self._connections:
            return
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(data)
            except (WebSocketDisconnect, RuntimeError, ConnectionError):
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)
