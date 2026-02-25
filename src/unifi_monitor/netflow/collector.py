# collector.py -- Async UDP NetFlow/IPFIX listener
# Receives packets, parses via parser.py, writes batches to DB.

from __future__ import annotations

import asyncio
import logging
import sqlite3
import threading
import time

from ..db import Database
from .parser import parse_packet

log = logging.getLogger(__name__)

MAX_PACKET_SIZE = 65535


class NetFlowProtocol(asyncio.DatagramProtocol):
    """Asyncio UDP protocol for NetFlow/IPFIX packets."""

    def __init__(self, db: Database, batch_interval: float = 10.0, site: str = "default") -> None:
        self.db = db
        self.site = site
        self.templates: dict = {"netflow": {}, "ipfix": {}}
        self.batch: list[dict] = []
        self._lock = threading.Lock()
        self.batch_interval = batch_interval
        self._last_flush = time.time()
        self._packets = 0
        self._flows = 0

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        if len(data) > MAX_PACKET_SIZE:
            log.warning("Oversized NetFlow packet (%d bytes) from %s, skipping", len(data), addr)
            return

        self._packets += 1
        flows = parse_packet(data, self.templates)
        if flows:
            with self._lock:
                self.batch.extend(flows)
                self._flows += len(flows)

        # Flush batch periodically
        now = time.time()
        if now - self._last_flush >= self.batch_interval:
            self._flush(now)

    def _flush(self, ts: float) -> None:
        with self._lock:
            if not self.batch:
                return
            batch_copy = list(self.batch)
            self.batch.clear()
        self._last_flush = ts
        try:
            self.db.insert_netflow_batch(ts, batch_copy, site=self.site)
        except sqlite3.OperationalError as e:
            log.warning("NetFlow DB write error: %s", e)

    def connection_lost(self, exc: Exception | None) -> None:
        self._flush(time.time())


async def start_collector(
    db: Database, host: str = "0.0.0.0", port: int = 2055, site: str = "default"
) -> asyncio.BaseTransport:
    """Start the NetFlow UDP listener. Returns the transport for cleanup."""
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: NetFlowProtocol(db, site=site),
        local_addr=(host, port),
    )
    log.info("NetFlow collector listening on %s:%d", host, port)

    # Periodic flush task
    async def periodic_flush() -> None:
        while True:
            await asyncio.sleep(protocol.batch_interval)
            protocol._flush(time.time())

    asyncio.create_task(periodic_flush())
    return transport
