# Contributing to UniFi Monitor

## Quick Setup

```bash
git clone https://github.com/matt-bloise/unifi-monitor.git
cd unifi-monitor
pip install -e ".[dev]"
cp .env.example .env
# Edit .env with your UniFi gateway credentials
python -m unifi_monitor
```

Dashboard at http://localhost:8080.

## Project Layout

```
src/unifi_monitor/
  app.py              FastAPI application + background task orchestration
  config.py           Environment variable config (no config files)
  db.py               SQLite storage (WAL mode, thread-safe)
  poller.py           Periodic UniFi API polling -> DB writes
  unifi_client.py     UniFi OS API wrapper (session reuse, CSRF)
  api/routes.py       REST endpoints for dashboard
  netflow/parser.py   IPFIX/NetFlow v5/v9 packet parser
  netflow/collector.py  Async UDP listener -> DB writes
  static/             Dashboard HTML/CSS/JS
```

## Architecture

Single-process, no external dependencies beyond the UniFi gateway:

1. **Poller** -- polls UniFi API every 30s, writes to SQLite
2. **NetFlow Collector** -- receives IPFIX/NetFlow UDP on port 2055, batch-writes to SQLite
3. **FastAPI** -- serves REST API + static dashboard
4. **SQLite** -- WAL mode for concurrent reads/writes, hourly retention cleanup

## Running Tests

```bash
python -m pytest tests/ -v
```

## Code Style

- Python 3.10+ type hints
- No third-party UniFi libraries (raw requests.Session)
- Keep dependencies minimal
- SQLite for storage (no external database required)

## Adding a New API Endpoint

1. Add a query method to `db.py`
2. Add a route in `api/routes.py`
3. Add frontend rendering in `static/js/dashboard.js`

## Adding a New Dashboard Panel

1. Add the HTML structure in `static/index.html`
2. Add the render function in `static/js/dashboard.js`
3. Wire it into the `refresh()` function
4. Add any needed API endpoint (see above)

## UniFi API Notes

- Endpoints under `/proxy/network/api/s/{site}/...` (UniFi OS, not legacy controller)
- Auth: `POST /api/auth/login`, CSRF via `X-Updated-CSRF-Token`
- 401 = session expired, auto-retry with re-auth
- Self-signed SSL certs: `verify=False` is expected
- Rate limit: ~5-6 rapid logins triggers 429 (session reuse prevents this)
