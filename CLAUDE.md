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
| `app.py` | FastAPI app, lifespan (starts poller + netflow + cleanup) |
| `config.py` | All config from env vars |
| `db.py` | SQLite schema, read/write methods, retention cleanup |
| `poller.py` | UniFi API polling loop, data parsing |
| `unifi_client.py` | UniFi OS API wrapper (session reuse, CSRF) |
| `api/routes.py` | REST endpoints (/api/overview, /api/clients, /api/traffic/*) |
| `netflow/parser.py` | IPFIX v10 + NetFlow v5/v9 packet parser |
| `netflow/collector.py` | Async UDP listener with batch DB writes |
| `static/` | Dashboard HTML/CSS/JS (Chart.js, vanilla JS) |

## Design Decisions

- **No Grafana/InfluxDB** -- SQLite is sufficient for single-network monitoring. One fewer container.
- **No config files** -- env vars only. Docker-native, no YAML to manage.
- **No third-party UniFi libs** -- raw requests.Session. Community libs are unmaintained.
- **IPFIX set-by-set parsing** -- UCG-Max sends mixed template/data packets. Library fails on unknown templates. Custom parser handles each set independently.
- **Session reuse** -- single UnifiClient instance, re-auth only on 401. Prevents 429 rate limiting.

## Common Commands

```bash
pip install -e ".[dev]"         # Dev install
python -m unifi_monitor         # Run locally
docker compose up -d --build    # Docker
make test                       # Tests
make lint                       # Compile check
```

## UniFi API

- Endpoints: `/proxy/network/api/s/{site}/...` (UniFi OS)
- Auth: `POST /api/auth/login`, CSRF via `X-Updated-CSRF-Token`
- 401 = session expired, auto re-auth
- Self-signed SSL: `verify=False` expected
- Rate limit: ~5-6 rapid logins -> 429 (session reuse prevents this)
