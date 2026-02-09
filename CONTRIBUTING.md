# Contributing to UniFi Monitor

## Quick Setup

```bash
git clone https://github.com/Matt-Bloise/unifi-monitor.git
cd unifi-monitor
pip install -e ".[dev,netflow]"
cp .env.example .env
# Edit .env with your UniFi gateway credentials
python -m unifi_monitor
```

Dashboard at http://localhost:8080.

## Project Layout

```
src/unifi_monitor/
  app.py              FastAPI application + background task orchestration
  config.py           Environment variable config with validation
  db.py               SQLite storage (WAL mode, thread-safe, compound indexes)
  poller.py           Periodic UniFi API polling -> DB writes + WS broadcast
  unifi_client.py     UniFi OS API wrapper (session reuse, CSRF, timeouts)
  ws.py               WebSocket broadcast hub (ConnectionManager)
  alerts.py           Alert rule evaluation + webhook notifications
  api/routes.py       REST + WebSocket endpoints with FastAPI dependency injection
  netflow/parser.py   IPFIX/NetFlow v5/v9 packet parser
  netflow/collector.py  Async UDP listener with thread-safe batch writes
  static/             Dashboard HTML/CSS/JS
```

## Architecture

Single-process, no external dependencies beyond the UniFi gateway:

1. **Poller** -- polls UniFi API every 30s, writes to SQLite, broadcasts snapshot via WebSocket
2. **Alert Engine** -- evaluates rules against each snapshot, sends webhook notifications
3. **NetFlow Collector** -- receives IPFIX/NetFlow UDP on port 2055, batch-writes to SQLite
4. **FastAPI** -- serves REST API + WebSocket + static dashboard, DI via `app.state`
5. **SQLite** -- WAL mode for concurrent reads/writes, hourly retention cleanup

## Running Tests

```bash
python -m pytest tests/ -v
```

Tests cover: database CRUD, API endpoints, data parsing, query validation, health score calculation, WebSocket broadcast, alert evaluation.

## Linting and Formatting

```bash
make lint       # ruff check
make format     # ruff format (auto-fix)
make check      # lint + format check (CI-equivalent)
```

Ruff config is in `pyproject.toml`. Target: Python 3.10+, 100-char line length.

## Code Style

- All modules use `from __future__ import annotations`
- Type annotations on all function signatures
- FastAPI dependency injection (not global state)
- Per-endpoint error isolation in poller (one failure doesn't skip others)
- Thread-safe batch operations in NetFlow collector

## Adding a New API Endpoint

1. Add a query method to `db.py`
2. Add a route in `api/routes.py` with `db: Database = Depends(get_db)`
3. Add `Query()` validation for any user-provided parameters
4. Wrap DB calls in try/except, return structured error JSON on failure
5. Add frontend rendering in `static/js/dashboard.js`
6. Add tests in `tests/test_api.py`

## Adding a New Dashboard Panel

1. Add the HTML structure in `static/index.html`
2. Add the render function in `static/js/dashboard.js`
3. Wire it into the `refresh()` function's `Promise.all`
4. If the panel should update via WebSocket, also wire it into the `wsConn.onmessage` handler
5. Add any needed API endpoint (see above)

## Adding an Alert Rule

Alert rules are defined in `src/unifi_monitor/alerts.py`.

1. If the metric already exists (see `_extract_metric()`), add a new `AlertRule` to `DEFAULT_RULES`:

```python
AlertRule("wan_latency", "gt", 200, "WAN latency critical: {value}ms", 600),
```

2. If you need a new metric, add extraction logic to `_extract_metric()`:

```python
if metric == "client_count":
    return overview.get("clients", {}).get("total", 0)
```

3. Available operators: `gt`, `lt`, `eq`, `ne`

4. The `message` template supports `{value}`, `{metric}`, and `{threshold}` placeholders.

5. `cooldown_s` sets the minimum seconds between repeated alerts for the same rule.

6. Add tests in `tests/test_alerts.py`:

```python
def test_my_new_rule(self) -> None:
    engine = AlertEngine(
        rules=[AlertRule("client_count", "gt", 20, "{value} clients", 0)],
    )
    snap = _make_snapshot(...)
    fired = engine.evaluate(snap)
    assert len(fired) == 1
```

## UniFi API Notes

- Endpoints under `/proxy/network/api/s/{site}/...` (UniFi OS, not legacy controller)
- Auth: `POST /api/auth/login`, CSRF via `X-Updated-CSRF-Token`
- 401 = session expired, auto-retry with re-auth
- Self-signed SSL certs: `verify=False` is expected
- Rate limit: ~5-6 rapid logins triggers 429 (session reuse prevents this)
- All requests have a 15s timeout
