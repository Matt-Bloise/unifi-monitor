# poller.py -- Periodic UniFi API polling
# Collects device/client/WAN data and writes to DB.
# Runs as an asyncio background task inside the FastAPI app.

import asyncio
import logging
import time

from .config import config
from .db import Database
from .unifi_client import UnifiClient, UnifiAPIError, UnifiAuthError

log = logging.getLogger(__name__)


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_wan(health_data: list) -> dict | None:
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


def _parse_device(d: dict) -> dict:
    name = d.get("name", d.get("hostname", d.get("mac", "unknown")))
    model = d.get("model", d.get("model_long_name", d.get("type", "unknown")))
    if isinstance(model, bool):
        model = d.get("model_long_name", d.get("type", "unknown"))
    sys_stats = d.get("system-stats", {})
    return {
        "mac": d.get("mac", ""),
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


def _parse_client(c: dict) -> dict:
    return {
        "mac": c.get("mac", ""),
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
    def __init__(self, db: Database):
        self.db = db
        self.client = UnifiClient(
            host=config.unifi_host,
            username=config.unifi_username,
            password=config.unifi_password,
            site=config.unifi_site,
            port=config.unifi_port,
        )
        self._running = False

    async def run(self):
        self._running = True
        log.info("Poller started (interval=%ds)", config.poll_interval)

        while self._running:
            try:
                await asyncio.to_thread(self._poll_cycle)
            except Exception as e:
                log.warning("Poll cycle error: %s", e)

            await asyncio.sleep(config.poll_interval)

    def stop(self):
        self._running = False

    def _poll_cycle(self):
        ts = time.time()
        self.client.ensure_auth()

        # WAN health
        try:
            health = self.client.get_health()
            wan = _parse_wan(health)
            if wan:
                self.db.insert_wan(
                    ts=ts, status=wan["status"], latency_ms=wan["latency_ms"],
                    wan_ip=wan["wan_ip"], cpu_pct=wan["cpu_pct"], mem_pct=wan["mem_pct"],
                    download_bps=wan.get("rx_bytes_r"), upload_bps=wan.get("tx_bytes_r"),
                )
        except (UnifiAPIError, UnifiAuthError) as e:
            log.warning("Health poll failed: %s", e)

        # Devices
        try:
            raw = self.client.get_devices()
            devices = [_parse_device(d) for d in raw]
            if devices:
                self.db.insert_devices(ts, devices)
        except (UnifiAPIError, UnifiAuthError) as e:
            log.warning("Device poll failed: %s", e)

        # Clients
        try:
            raw = self.client.get_clients()
            clients = [_parse_client(c) for c in raw]
            if clients:
                self.db.insert_clients(ts, clients)
        except (UnifiAPIError, UnifiAuthError) as e:
            log.warning("Client poll failed: %s", e)

        # Alarms
        try:
            raw = self.client.get_alarms()
            alarms = [_parse_alarm(a) for a in raw]
            if alarms:
                self.db.insert_alarms(ts, alarms)
        except (UnifiAPIError, UnifiAuthError) as e:
            log.warning("Alarm poll failed: %s", e)
