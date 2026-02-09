# UniFi Monitor -- Project Context

Real-time network monitoring dashboard for UniFi networks. Single container, zero external dependencies beyond the gateway.

## Architecture

Single-process Python app:
- **FastAPI** serves REST API + static dashboard on port 8080
- **Poller** hits UniFi API every 30s, writes to SQLite
- **NetFlow Collector** receives IPFIX/NetFlow UDP on port 2055, batch-writes to SQLite
- **SQLite** with WAL mode for concurrent reads/writes

All source in `src/unifi_monitor/` -- installable via `pip install -e .`.

## Key Files

| File | Purpose |
|------|---------|
| `app.py` | FastAPI app, lifespan (starts poller + netflow + cleanup), DI via `app.state` |
| `config.py` | All config from env vars with bounds validation |
| `db.py` | SQLite schema, read/write methods, retention cleanup, `get_db_stats()` |
| `poller.py` | UniFi API polling loop, data parsing, per-endpoint error isolation |
| `unifi_client.py` | UniFi OS API wrapper (session reuse, CSRF, 15s timeouts) |
| `api/routes.py` | REST endpoints with FastAPI DI, query validation, `/api/health` |
| `netflow/parser.py` | IPFIX v10 + NetFlow v5/v9 packet parser |
| `netflow/collector.py` | Async UDP listener with thread-safe batch writes |
| `static/` | Dashboard HTML/CSS/JS (Chart.js, vanilla JS) |

## Design Decisions

- **No Grafana/InfluxDB** -- SQLite is sufficient for single-network monitoring. One fewer container.
- **No config files** -- env vars only. Docker-native, no YAML to manage.
- **No third-party UniFi libs** -- raw requests.Session. Community libs are unmaintained.
- **IPFIX set-by-set parsing** -- UCG-Max sends mixed template/data packets. Library fails on unknown templates. Custom parser handles each set independently.
- **Session reuse** -- single UnifiClient instance, re-auth only on 401. Prevents 429 rate limiting.
- **FastAPI dependency injection** -- DB passed via `app.state`, not global variable injection.
- **Weighted health score** -- WAN (40%), devices (30%), alarms (30%) with documented factors.
- **netflow is optional** -- moved to `[project.optional-dependencies]`, not required for basic monitoring.

## Known Limitations

- No authentication on the dashboard (bind to localhost or use a reverse proxy)
- No WebSocket support (frontend polls every 15s)
- Single-site only (no multi-site UniFi support)
- NetFlow parser requires the `netflow` package (`pip install -e ".[netflow]"`)
- SQLite not suitable for multi-process writes (single-process design)

## Common Commands

```bash
pip install -e ".[dev,netflow]"    # Dev install
python -m unifi_monitor            # Run locally
docker compose up -d --build       # Docker
make test                          # Tests
make lint                          # Ruff lint check
make check                         # Lint + format check
```

## UniFi API

- Endpoints: `/proxy/network/api/s/{site}/...` (UniFi OS)
- Auth: `POST /api/auth/login`, CSRF via `X-Updated-CSRF-Token`
- 401 = session expired, auto re-auth
- Self-signed SSL: `verify=False` expected
- Rate limit: ~5-6 rapid logins -> 429 (session reuse prevents this)
- All requests have 15s timeout
