# poller.py -- Periodic UniFi API polling
# Collects device/client/WAN data and writes to DB.
# Runs as an asyncio background task inside the FastAPI app.

from __future__ import annotations

import asyncio
import logging
import time

from .config import config
from .db import Database
from .unifi_client import UnifiAPIError, UnifiAuthError, UnifiClient

log = logging.getLogger(__name__)


def _safe_int(val: object) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val: object) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_wan(health_data: list[dict]) -> dict | None:
    for sub in health_data:
        if sub.get("subsystem") == "wan":
            sys_stats = sub.get("gw_system-stats", {})
            return {
                "status": sub.get("status", "unknown"),
                "wan_ip": sub.get("wan_ip", sub.get("gw_wan_ip")),
                "latency_ms": _safe_float(sub.get("latency")),
                "cpu_pct": _safe_float(sys_stats.get("cpu")),
                "mem_pct": _safe_float(sys_stats.get("mem")),
                "tx_bytes_r": sub.get("tx_bytes-r"),
                "rx_bytes_r": sub.get("rx_bytes-r"),
            }
    return None


def _parse_device(d: dict) -> dict | None:
    mac = d.get("mac")
    if not mac:
        log.debug("Skipping device with no MAC: %s", d.get("name", "unknown"))
        return None
    name = d.get("name", d.get("hostname", d.get("mac", "unknown")))
    model = d.get("model", d.get("model_long_name", d.get("type", "unknown")))
    if isinstance(model, bool):
        model = d.get("model_long_name", d.get("type", "unknown"))
    sys_stats = d.get("system-stats", {})
    return {
        "mac": mac,
        "name": str(name),
        "model": str(model),
        "ip": d.get("ip"),
        "state": d.get("state", 0),
        "cpu_pct": _safe_float(sys_stats.get("cpu")),
        "mem_pct": _safe_float(sys_stats.get("mem")),
        "num_clients": d.get("num_sta", 0),
        "satisfaction": _safe_int(d.get("satisfaction")),
        "tx_bytes_r": _safe_float(d.get("tx_bytes-r")),
        "rx_bytes_r": _safe_float(d.get("rx_bytes-r")),
    }


def _parse_client(c: dict) -> dict | None:
    mac = c.get("mac")
    if not mac:
        log.debug("Skipping client with no MAC")
        return None
    return {
        "mac": mac,
        "hostname": c.get("hostname", c.get("name", c.get("oui", c.get("mac", "unknown")))),
        "ip": c.get("ip"),
        "is_wired": bool(c.get("is_wired", False)),
        "ssid": c.get("essid"),
        "signal_dbm": _safe_int(c.get("signal")),
        "satisfaction": _safe_int(c.get("satisfaction")),
        "channel": _safe_int(c.get("channel")),
        "radio": c.get("radio"),
        "tx_bytes": c.get("tx_bytes", 0) or 0,
        "rx_bytes": c.get("rx_bytes", 0) or 0,
        "tx_rate": _safe_float(c.get("tx_rate", c.get("tx_bytes-r"))),
        "rx_rate": _safe_float(c.get("rx_rate", c.get("rx_bytes-r"))),
    }


def _parse_alarm(a: dict) -> dict:
    return {
        "id": a.get("_id"),
        "type": a.get("type", a.get("key", "unknown")),
        "message": a.get("msg", a.get("message", "")),
        "device_name": a.get("device_name", a.get("ap_name")),
        "archived": bool(a.get("archived", False)),
    }


class Poller:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.client = UnifiClient(
            host=config.unifi_host,
            username=config.unifi_username,
            password=config.unifi_password,
            site=config.unifi_site,
            port=config.unifi_port,
        )
        self._running = False
        self._success_count = 0
        self._error_count = 0
        self._cycle_count = 0

    async def run(self) -> None:
        self._running = True
        log.info("Poller started (interval=%ds)", config.poll_interval)

        while self._running:
            try:
                await asyncio.to_thread(self._poll_cycle)
            except Exception as e:
                log.warning("Poll cycle error: %s", e)

            await asyncio.sleep(config.poll_interval)

    def stop(self) -> None:
        self._running = False
        self.client.close()

    def _poll_cycle(self) -> None:
        ts = time.time()
        self._cycle_count += 1
        self.client.ensure_auth()

        poll_methods = [
            ("health", self._poll_health),
            ("devices", self._poll_devices),
            ("clients", self._poll_clients),
            ("alarms", self._poll_alarms),
        ]

        for name, method in poll_methods:
            try:
                method(ts)
                self._success_count += 1
            except (UnifiAPIError, UnifiAuthError) as e:
                log.warning("%s poll failed: %s", name.capitalize(), e)

                self._error_count += 1
            except Exception as e:
                log.warning("%s poll failed (unexpected): %s", name.capitalize(), e)

                self._error_count += 1

        if self._cycle_count % 10 == 0:
            log.info(
                "Poll stats: %d cycles, %d successes, %d errors",
                self._cycle_count,
                self._success_count,
                self._error_count,
            )

    def _poll_health(self, ts: float) -> None:
        health = self.client.get_health()
        wan = _parse_wan(health)
        if wan:
            self.db.insert_wan(
                ts=ts,
                status=wan["status"],
                latency_ms=wan["latency_ms"],
                wan_ip=wan["wan_ip"],
                cpu_pct=wan["cpu_pct"],
                mem_pct=wan["mem_pct"],
                download_bps=wan.get("rx_bytes_r"),
                upload_bps=wan.get("tx_bytes_r"),
            )

    def _poll_devices(self, ts: float) -> None:
        raw = self.client.get_devices()
        devices = [d for d in (_parse_device(r) for r in raw) if d is not None]
        if devices:
            self.db.insert_devices(ts, devices)

    def _poll_clients(self, ts: float) -> None:
        raw = self.client.get_clients()
        clients = [c for c in (_parse_client(r) for r in raw) if c is not None]
        if clients:
            self.db.insert_clients(ts, clients)

    def _poll_alarms(self, ts: float) -> None:
        raw = self.client.get_alarms()
        alarms = [_parse_alarm(a) for a in raw]
        if alarms:
            self.db.insert_alarms(ts, alarms)
