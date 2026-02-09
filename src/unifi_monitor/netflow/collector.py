# collector.py -- Async UDP NetFlow/IPFIX listener
# Receives packets, parses via parser.py, writes batches to DB.

import asyncio
import logging
import time

from ..db import Database
from .parser import parse_packet

log = logging.getLogger(__name__)


class NetFlowProtocol(asyncio.DatagramProtocol):
    """Asyncio UDP protocol for NetFlow/IPFIX packets."""

    def __init__(self, db: Database, batch_interval: float = 10.0):
        self.db = db
        self.templates: dict = {"netflow": {}, "ipfix": {}}
        self.batch: list[dict] = []
        self.batch_interval = batch_interval
        self._last_flush = time.time()
        self._packets = 0
        self._flows = 0

    def datagram_received(self, data: bytes, addr: tuple):
        self._packets += 1
        flows = parse_packet(data, self.templates)
        if flows:
            self.batch.extend(flows)
            self._flows += len(flows)

        # Flush batch periodically
        now = time.time()
        if now - self._last_flush >= self.batch_interval and self.batch:
            self._flush(now)

    def _flush(self, ts: float):
        if not self.batch:
            return
        try:
            self.db.insert_netflow_batch(ts, self.batch)
        except Exception as e:
            log.warning("NetFlow DB write error: %s", e)
        self.batch.clear()
        self._last_flush = ts

    def connection_lost(self, exc):
        if self.batch:
            self._flush(time.time())


async def start_collector(db: Database, host: str = "0.0.0.0", port: int = 2055):
    """Start the NetFlow UDP listener. Returns the transport for cleanup."""
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: NetFlowProtocol(db),
        local_addr=(host, port),
    )
    log.info("NetFlow collector listening on %s:%d", host, port)

    # Periodic flush task
    async def periodic_flush():
        while True:
            await asyncio.sleep(protocol.batch_interval)
            if protocol.batch:
                protocol._flush(time.time())

    asyncio.create_task(periodic_flush())
    return transport
