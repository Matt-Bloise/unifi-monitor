# routes.py -- REST API endpoints for the dashboard
# All endpoints return JSON. The frontend fetches these via /api/*.

from __future__ import annotations

import csv
import hashlib
import io
import secrets
import sqlite3
import time
from typing import Any

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse

from ..config import config
from ..db import Database

router = APIRouter(prefix="/api")


def _ws_token(hour_offset: int = 0) -> str:
    """Generate an hour-based WS auth token. Accepts current and previous hour."""
    hour = int(time.time() // 3600) + hour_offset
    raw = f"{config.auth_username}:{config.auth_password}:{hour}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


PROTO_MAP = {1: "ICMP", 6: "TCP", 17: "UDP", 47: "GRE", 50: "ESP", 58: "ICMPv6"}


def get_db(request: Request) -> Database:
    """FastAPI dependency: get the Database from app.state."""
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise RuntimeError("Database not initialized")
    return db


def get_site(request: Request, site: str = Query(None)) -> str:
    """FastAPI dependency: resolve the active site name."""
    sites = getattr(request.app.state, "sites", ["default"])
    if site is None or site not in sites:
        return sites[0]
    return site


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


def _compute_health(wan: dict | None, devices: list[dict], alarms: list[dict]) -> dict[str, Any]:
    """Weighted health score with documented factors."""
    score = 100
    factors: list[str] = []

    # WAN status (40% weight)
    if not wan or wan.get("status") != "ok":
        score -= 40
        factors.append("WAN down")
    elif wan.get("latency_ms") and wan["latency_ms"] > 100:
        score -= 15
        factors.append(f"High latency ({wan['latency_ms']:.0f}ms)")
    elif wan.get("latency_ms") and wan["latency_ms"] > 50:
        score -= 5
        factors.append(f"Elevated latency ({wan['latency_ms']:.0f}ms)")

    # Device health (30% weight)
    offline = [d for d in devices if d.get("state") != 1]
    if offline:
        penalty = min(30, 15 * len(offline))
        score -= penalty
        factors.append(f"{len(offline)} device(s) offline")

    # Alarms (30% weight)
    alarm_penalty = min(30, 5 * len(alarms))
    if alarm_penalty:
        score -= alarm_penalty
        factors.append(f"{len(alarms)} active alarm(s)")

    return {"score": max(0, score), "factors": factors}


@router.get("/health")
def health_check(request: Request) -> dict:
    """Health endpoint for Docker healthcheck and monitoring."""
    db = getattr(request.app.state, "db", None)
    start_time = getattr(request.app.state, "start_time", 0)
    result: dict[str, Any] = {
        "status": "ok",
        "uptime_s": round(time.time() - start_time, 1),
    }
    if db is not None:
        try:
            stats = db.get_db_stats()
            result["last_write_ts"] = stats.get("last_write_ts", 0)
            result["db_size_bytes"] = stats.get("db_size_bytes", 0)
        except sqlite3.OperationalError:
            result["status"] = "degraded"
    else:
        result["status"] = "starting"
    return result


@router.get("/auth/token")
def auth_token() -> dict:
    """Return a WS auth token. Requires valid Basic Auth (enforced by middleware)."""
    if not config.auth_username or not config.auth_password:
        return {"token": ""}
    return {"token": _ws_token()}


@router.get("/sites")
def list_sites(request: Request) -> dict:
    """Return configured site list and default site."""
    sites = getattr(request.app.state, "sites", ["default"])
    return {"sites": sites, "default": sites[0]}


@router.get("/overview")
def overview(db: Database = Depends(get_db), site: str = Depends(get_site)) -> dict:
    """Dashboard overview: WAN status, device/client counts, health score."""
    try:
        wan = db.get_latest_wan(site=site)
        devices = db.get_latest_devices(site=site)
        clients = db.get_latest_clients(site=site)
        alarms = db.get_active_alarms(site=site)
    except sqlite3.OperationalError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

    wireless_clients = [c for c in clients if not c.get("is_wired")]
    wired_clients = [c for c in clients if c.get("is_wired")]

    health = _compute_health(wan, devices, alarms)

    return {
        "health_score": health["score"],
        "health_factors": health["factors"],
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
def get_clients(
    db: Database = Depends(get_db),
    site: str = Depends(get_site),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    """All connected clients with stats, paginated."""
    try:
        clients = db.get_latest_clients(site=site)
    except sqlite3.OperationalError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    clients.sort(key=lambda c: c.get("rx_bytes") or 0, reverse=True)
    return {
        "total": len(clients),
        "offset": offset,
        "limit": limit,
        "data": clients[offset : offset + limit],
    }


@router.get("/clients/{mac}/history")
def client_history(
    mac: str,
    db: Database = Depends(get_db),
    site: str = Depends(get_site),
    hours: float = Query(24, ge=0.1, le=8760),
) -> list[dict]:
    """Signal/satisfaction history for a specific client."""
    try:
        return db.get_client_history(mac, hours, site=site)
    except sqlite3.OperationalError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/devices")
def get_devices(db: Database = Depends(get_db), site: str = Depends(get_site)) -> list[dict]:
    """All adopted devices with stats."""
    try:
        return db.get_latest_devices(site=site)
    except sqlite3.OperationalError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/wan/history")
def wan_history(
    db: Database = Depends(get_db),
    site: str = Depends(get_site),
    hours: float = Query(24, ge=0.1, le=8760),
) -> list[dict]:
    """WAN latency and status history."""
    try:
        return db.get_wan_history(hours, site=site)
    except sqlite3.OperationalError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/traffic/top-talkers")
def top_talkers(
    db: Database = Depends(get_db),
    site: str = Depends(get_site),
    hours: float = Query(1, ge=0.1, le=8760),
    limit: int = Query(20, ge=1, le=1000),
) -> list[dict]:
    """Top source IPs by bytes (NetFlow data)."""
    try:
        rows = db.get_top_talkers(hours, limit, site=site)
    except sqlite3.OperationalError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    for r in rows:
        r["total_bytes_fmt"] = _fmt_bytes(r.get("total_bytes"))
    return rows


@router.get("/traffic/top-destinations")
def top_destinations(
    db: Database = Depends(get_db),
    site: str = Depends(get_site),
    hours: float = Query(1, ge=0.1, le=8760),
    limit: int = Query(20, ge=1, le=1000),
) -> list[dict]:
    """Top destination IPs by bytes (NetFlow data)."""
    try:
        rows = db.get_top_destinations(hours, limit, site=site)
    except sqlite3.OperationalError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    for r in rows:
        r["total_bytes_fmt"] = _fmt_bytes(r.get("total_bytes"))
    return rows


@router.get("/traffic/top-ports")
def top_ports(
    db: Database = Depends(get_db),
    site: str = Depends(get_site),
    hours: float = Query(1, ge=0.1, le=8760),
    limit: int = Query(20, ge=1, le=1000),
) -> list[dict]:
    """Top destination ports by bytes."""
    try:
        rows = db.get_top_ports(hours, limit, site=site)
    except sqlite3.OperationalError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    for r in rows:
        r["total_bytes_fmt"] = _fmt_bytes(r.get("total_bytes"))
        r["protocol_name"] = PROTO_MAP.get(r.get("protocol"), str(r.get("protocol", "")))
    return rows


@router.get("/traffic/dns-queries")
def dns_queries(
    db: Database = Depends(get_db),
    site: str = Depends(get_site),
    hours: float = Query(1, ge=0.1, le=8760),
    limit: int = Query(100, ge=1, le=1000),
) -> list[dict]:
    """DNS query aggregates: per-client-per-server."""
    try:
        rows = db.get_dns_queries(hours, limit, site=site)
    except sqlite3.OperationalError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    for r in rows:
        r["total_bytes_fmt"] = _fmt_bytes(r.get("total_bytes"))
    return rows


@router.get("/traffic/dns-top-clients")
def dns_top_clients(
    db: Database = Depends(get_db),
    site: str = Depends(get_site),
    hours: float = Query(1, ge=0.1, le=8760),
    limit: int = Query(20, ge=1, le=1000),
) -> list[dict]:
    """Top DNS-querying clients by flow count."""
    try:
        rows = db.get_dns_top_clients(hours, limit, site=site)
    except sqlite3.OperationalError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    for r in rows:
        r["total_bytes_fmt"] = _fmt_bytes(r.get("total_bytes"))
    return rows


@router.get("/traffic/dns-top-servers")
def dns_top_servers(
    db: Database = Depends(get_db),
    site: str = Depends(get_site),
    hours: float = Query(1, ge=0.1, le=8760),
    limit: int = Query(20, ge=1, le=1000),
) -> list[dict]:
    """Top DNS servers by flow count."""
    try:
        rows = db.get_dns_top_servers(hours, limit, site=site)
    except sqlite3.OperationalError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    for r in rows:
        r["total_bytes_fmt"] = _fmt_bytes(r.get("total_bytes"))
    return rows


@router.get("/traffic/bandwidth")
def bandwidth_timeseries(
    db: Database = Depends(get_db),
    site: str = Depends(get_site),
    hours: float = Query(24, ge=0.1, le=8760),
    bucket_minutes: int = Query(5, ge=1, le=1440),
) -> list[dict]:
    """Bandwidth over time in configurable buckets."""
    try:
        rows = db.get_bandwidth_timeseries(hours, bucket_minutes, site=site)
    except sqlite3.OperationalError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    for r in rows:
        r["mbps"] = round((r.get("total_bytes", 0) * 8) / (bucket_minutes * 60 * 1_000_000), 2)
    return rows


@router.get("/compare")
def compare(
    db: Database = Depends(get_db),
    site: str = Depends(get_site),
    metric: str = Query(..., pattern=r"^(latency|bandwidth|client_count)$"),
    hours: float = Query(24, ge=1, le=8760),
    offset_hours: float = Query(168, ge=1, le=8760),
) -> dict:
    """Historical comparison: current window vs previous window."""
    return db.get_comparison(metric, hours, offset_hours, site=site)


@router.get("/alarms")
def get_alarms(db: Database = Depends(get_db), site: str = Depends(get_site)) -> list[dict]:
    """Active (non-archived) alarms."""
    try:
        return db.get_active_alarms(site=site)
    except sqlite3.OperationalError as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


def _csv_response(rows: list[dict], name: str) -> StreamingResponse:
    """Build a CSV streaming response from a list of dicts."""
    buf = io.StringIO()
    if not rows:
        buf.write("no data\n")
    else:
        writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
    )


@router.get("/export/clients")
def export_clients(
    db: Database = Depends(get_db),
    site: str = Depends(get_site),
    hours: float = Query(24, ge=0.1, le=8760),
    format: str = Query("json", pattern=r"^(json|csv)$"),
    limit: int = Query(10000, ge=1, le=10000),
) -> Any:
    """Export client data as JSON or CSV."""
    rows = db.get_clients_export(hours, limit, site=site)
    if format == "csv":
        return _csv_response(rows, "clients")
    return rows


@router.get("/export/wan")
def export_wan(
    db: Database = Depends(get_db),
    site: str = Depends(get_site),
    hours: float = Query(24, ge=0.1, le=8760),
    format: str = Query("json", pattern=r"^(json|csv)$"),
    limit: int = Query(10000, ge=1, le=10000),
) -> Any:
    """Export WAN metrics as JSON or CSV."""
    rows = db.get_wan_export(hours, limit, site=site)
    if format == "csv":
        return _csv_response(rows, "wan")
    return rows


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for live dashboard updates."""
    # Auth check for WebSocket (middleware doesn't intercept WS scope)
    if config.auth_username and config.auth_password:
        token = websocket.query_params.get("token", "")
        valid = secrets.compare_digest(token, _ws_token(0)) or secrets.compare_digest(
            token, _ws_token(-1)
        )
        if not valid:
            await websocket.close(code=4001, reason="Unauthorized")
            return

    manager = websocket.app.state.ws_manager
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keepalive
    except WebSocketDisconnect:
        manager.disconnect(websocket)
