# api

FastAPI route definitions for the REST API and WebSocket endpoint.

## Modules

| Module | Lines | Purpose |
|--------|-------|---------|
| `routes.py` | 434 | 18 REST endpoints + 1 WebSocket endpoint |
| `__init__.py` | - | Package marker |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (bypasses auth) |
| GET | `/api/auth/token` | WebSocket auth token |
| GET | `/api/sites` | Configured site list |
| GET | `/api/overview` | Dashboard summary with health score |
| GET | `/api/clients` | Connected clients (paginated) |
| GET | `/api/clients/{mac}/history` | Client signal/satisfaction history |
| GET | `/api/devices` | Adopted devices |
| GET | `/api/wan/history` | WAN latency/status history |
| GET | `/api/traffic/top-talkers` | Top source IPs by bytes |
| GET | `/api/traffic/top-destinations` | Top destination IPs |
| GET | `/api/traffic/top-ports` | Top ports by bytes |
| GET | `/api/traffic/bandwidth` | Bandwidth timeseries |
| GET | `/api/traffic/dns-queries` | DNS query aggregates |
| GET | `/api/traffic/dns-top-clients` | Top DNS clients |
| GET | `/api/traffic/dns-top-servers` | Top DNS servers |
| GET | `/api/compare` | Historical comparison |
| GET | `/api/alarms` | Active alarms |
| GET | `/api/export/clients` | Export client data (JSON/CSV) |
| GET | `/api/export/wan` | Export WAN metrics (JSON/CSV) |
| WS | `/api/ws` | Live dashboard updates |

## Dependency Injection

Database access uses FastAPI's `app.state` pattern:

```python
def get_db(request: Request) -> Database:
    return request.app.state.db
```

The `Database` instance is created during app lifespan and injected into route handlers via `Depends(get_db)`.

Multi-site support: all endpoints accept an optional `?site=` query parameter, passed through to DB queries.

## Authentication

When `AUTH_USERNAME` and `AUTH_PASSWORD` are set, `BasicAuthMiddleware` in `app.py` protects all routes except `/api/health`.

WebSocket auth uses an hour-based SHA-256 token obtained from `GET /api/auth/token`.

## CSV Export

The `/api/export/clients` and `/api/export/wan` endpoints support `?format=csv`, returning a `text/csv` response with `Content-Disposition: attachment` header.
