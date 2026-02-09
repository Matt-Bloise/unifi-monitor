# unifi_monitor

Core Python package for UniFi Monitor.

## Entry Point

```bash
python -m unifi_monitor          # Starts FastAPI + poller + NetFlow collector
```

Or via the installed script:

```bash
unifi-monitor
```

Both call `app.main()` which starts uvicorn with the FastAPI application.

## Modules

| Module | Lines | Purpose |
|--------|-------|---------|
| `app.py` | 176 | FastAPI application with lifespan management, BasicAuthMiddleware, static file serving |
| `config.py` | 78 | Environment variable loading with bounds validation (`_safe_int` helper) |
| `db.py` | 527 | SQLite storage: 5 tables (WAL mode), CRUD, retention cleanup, historical comparison |
| `poller.py` | 278 | Periodic UniFi API polling, per-endpoint error isolation, WS broadcast, alert eval |
| `unifi_client.py` | 124 | UniFi OS API wrapper: session reuse, CSRF handling, 401 auto-retry, 15s timeout |
| `ws.py` | 39 | WebSocket broadcast hub (in-memory ConnectionManager) |
| `alerts.py` | 138 | Alert rule evaluation + webhook POST with per-rule cooldowns |
| `__init__.py` | 4 | Version string (`__version__ = "0.4.0"`) |
| `__main__.py` | 6 | Entry point for `python -m unifi_monitor` |

## Sub-Packages

| Package | Purpose |
|---------|---------|
| [`api/`](api/README.md) | REST + WebSocket route definitions (FastAPI router) |
| [`netflow/`](netflow/README.md) | IPFIX/NetFlow UDP collector and parser |
| [`static/`](static/README.md) | Dashboard frontend (HTML, CSS, JS) |

## Architecture

```
app.py (lifespan)
 ├── poller.py ── unifi_client.py ── UniFi gateway API
 │   ├── db.py (write snapshot)
 │   ├── ws.py (broadcast to dashboard)
 │   └── alerts.py (evaluate rules, webhook)
 ├── netflow/collector.py ── netflow/parser.py ── UDP 2055
 │   └── db.py (batch write flows)
 └── api/routes.py ── db.py (read queries)
     └── static/ (served at /)
```

## Configuration

All settings via environment variables. See `config.py` or the [configuration docs](../../docs/configuration.md).
