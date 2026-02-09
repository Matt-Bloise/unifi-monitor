# routes.py -- REST API endpoints for the dashboard
# All endpoints return JSON. The frontend fetches these via /api/*.

import time
from fastapi import APIRouter

from ..db import Database

router = APIRouter(prefix="/api")

# Injected by app.py at startup
db: Database | None = None

PROTO_MAP = {1: "ICMP", 6: "TCP", 17: "UDP", 47: "GRE", 50: "ESP", 58: "ICMPv6"}


def _fmt_bytes(b: int | float | None) -> str:
    if not b:
        return "0 B"
    b = float(b)
    if b >= 1_073_741_824:
        return f"{b / 1_073_741_824:.1f} GB"
    if b >= 1_048_576:
        return f"{b / 1_048_576:.1f} MB"
    if b >= 1024:
        return f"{b / 1024:.1f} KB"
    return f"{b:.0f} B"


@router.get("/overview")
def overview():
    """Dashboard overview: WAN status, device/client counts, health score."""
    wan = db.get_latest_wan()
    devices = db.get_latest_devices()
    clients = db.get_latest_clients()
    alarms = db.get_active_alarms()

    wireless_clients = [c for c in clients if not c.get("is_wired")]
    wired_clients = [c for c in clients if c.get("is_wired")]

    # Simple health score (0-100)
    score = 100
    if not wan or wan.get("status") != "ok":
        score -= 40
    if wan and wan.get("latency_ms") and wan["latency_ms"] > 50:
        score -= 10
    for d in devices:
        if d.get("state") != 1:
            score -= 20
    score -= len(alarms) * 5
    score = max(0, min(100, score))

    return {
        "health_score": score,
        "wan": {
            "status": wan.get("status", "unknown") if wan else "no data",
            "latency_ms": round(wan["latency_ms"], 1) if wan and wan.get("latency_ms") else None,
            "wan_ip": wan.get("wan_ip") if wan else None,
            "cpu_pct": round(wan["cpu_pct"], 1) if wan and wan.get("cpu_pct") else None,
            "mem_pct": round(wan["mem_pct"], 1) if wan and wan.get("mem_pct") else None,
        },
        "devices": {
            "total": len(devices),
            "online": sum(1 for d in devices if d.get("state") == 1),
        },
        "clients": {
            "total": len(clients),
            "wireless": len(wireless_clients),
            "wired": len(wired_clients),
        },
        "alarms": len(alarms),
        "timestamp": time.time(),
    }


@router.get("/clients")
def get_clients():
    """All connected clients with stats."""
    clients = db.get_latest_clients()
    return sorted(clients, key=lambda c: c.get("rx_bytes") or 0, reverse=True)


@router.get("/clients/{mac}/history")
def client_history(mac: str, hours: float = 24):
    """Signal/satisfaction history for a specific client."""
    return db.get_client_history(mac, hours)


@router.get("/devices")
def get_devices():
    """All adopted devices with stats."""
    return db.get_latest_devices()


@router.get("/wan/history")
def wan_history(hours: float = 24):
    """WAN latency and status history."""
    return db.get_wan_history(hours)


@router.get("/traffic/top-talkers")
def top_talkers(hours: float = 1, limit: int = 20):
    """Top source IPs by bytes (NetFlow data)."""
    rows = db.get_top_talkers(hours, limit)
    for r in rows:
        r["total_bytes_fmt"] = _fmt_bytes(r.get("total_bytes"))
    return rows


@router.get("/traffic/top-destinations")
def top_destinations(hours: float = 1, limit: int = 20):
    """Top destination IPs by bytes (NetFlow data)."""
    rows = db.get_top_destinations(hours, limit)
    for r in rows:
        r["total_bytes_fmt"] = _fmt_bytes(r.get("total_bytes"))
    return rows


@router.get("/traffic/top-ports")
def top_ports(hours: float = 1, limit: int = 20):
    """Top destination ports by bytes."""
    rows = db.get_top_ports(hours, limit)
    for r in rows:
        r["total_bytes_fmt"] = _fmt_bytes(r.get("total_bytes"))
        r["protocol_name"] = PROTO_MAP.get(r.get("protocol"), str(r.get("protocol", "")))
    return rows


@router.get("/traffic/bandwidth")
def bandwidth_timeseries(hours: float = 24, bucket_minutes: int = 5):
    """Bandwidth over time in configurable buckets."""
    rows = db.get_bandwidth_timeseries(hours, bucket_minutes)
    for r in rows:
        r["mbps"] = round((r.get("total_bytes", 0) * 8) / (bucket_minutes * 60 * 1_000_000), 2)
    return rows


@router.get("/alarms")
def get_alarms():
    """Active (non-archived) alarms."""
    return db.get_active_alarms()
