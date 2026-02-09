# UniFi Monitor

Real-time network monitoring dashboard for UniFi networks. One container, zero external dependencies beyond your gateway.

[![CI](https://github.com/Matt-Bloise/unifi-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/Matt-Bloise/unifi-monitor/actions/workflows/ci.yml)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)

## Quick Start

```bash
git clone https://github.com/Matt-Bloise/unifi-monitor.git
cd unifi-monitor
cp .env.example .env
# Edit .env: set UNIFI_HOST, UNIFI_USERNAME, UNIFI_PASSWORD
docker compose up -d
```

Dashboard at **http://localhost:8080**.

> **Security note:** Set `AUTH_USERNAME` and `AUTH_PASSWORD` to enable HTTP Basic Auth. Without auth, bind to `localhost` or place behind a reverse proxy if exposed beyond your local network.

## Features

- **Live dashboard** -- health score, connected clients, WAN latency, device status, active alarms
- **WebSocket updates** -- dashboard updates instantly when poller completes (no 15s polling lag)
- **Per-client drill-down** -- click any client row for 24h signal strength and satisfaction charts
- **Alert notifications** -- configurable thresholds with webhook delivery (Discord, Slack, ntfy)
- **NetFlow/IPFIX visualization** -- top talkers, bandwidth over time, port/protocol breakdown
- **Client monitoring** -- signal strength, satisfaction scores, per-client bandwidth, sortable columns
- **WAN tracking** -- latency history, status changes, gateway CPU/memory
- **Device status** -- gateway + AP cards with online/offline badges
- **Connection resilience** -- auto-reconnect with exponential backoff, REST polling fallback
- **DNS traffic analysis** -- top DNS clients and servers from NetFlow data (port 53/853)
- **Multi-site support** -- monitor multiple UniFi sites with site selector dropdown
- **Historical comparison** -- compare latency, bandwidth, or client count vs last week with Chart.js overlay
- **Data export** -- download client or WAN data as CSV or JSON from the dashboard
- **Dark/light theme** -- toggle between dark and light mode (persisted in browser)
- **Auto-pause** -- stops updates when browser tab is hidden
- **Docker healthcheck** -- `/api/health` endpoint for monitoring
- **Zero dependencies** -- no Grafana, no InfluxDB, no external database. SQLite + one container.

## Architecture

```
┌──────────────────────────────────────────┐
│            unifi-monitor                 │
│                                          │
│  ┌──────────┐    ┌───────────────┐       │
│  │  Poller   │──>│   SQLite DB   │       │
│  │(UniFi API)│    │  (WAL mode)   │       │
│  └────┬─────┘    └──────┬────────┘       │
│       │                 │                │
│       ├─> WS Broadcast  │                │
│       └─> Alert Engine  │                │
│                         │                │
│  ┌──────────┐           │                │
│  │ NetFlow  │───────────┘                │
│  │(UDP 2055)│                            │
│  └──────────┘    ┌──────┴────────┐       │
│                  │   FastAPI     │       │
│                  │ REST + WS     │──── :8080
│                  └───────────────┘       │
└──────────────────────────────────────────┘
```

## WebSocket

The dashboard auto-connects via WebSocket at `/api/ws`. When the poller completes a cycle, it broadcasts the latest snapshot to all connected clients instantly.

- **Live mode**: green badge, data arrives as soon as poller finishes
- **Polling fallback**: if WebSocket fails 3 times, falls back to 15s REST polling (yellow badge)
- **Auto-reconnect**: exponential backoff (1s -> 2s -> 4s -> ... -> 30s max)
- **Tab-aware**: pauses WS connection when browser tab is hidden

## Alerts

Set `ALERT_WEBHOOK_URL` to enable alert notifications. Default rules fire on:

- WAN down
- Health score below 50
- Device(s) offline
- WAN latency above 100ms

Per-rule cooldowns prevent notification spam (default 5 minutes).

Webhook payload format (works with Discord webhooks, Slack incoming webhooks, ntfy, httpbin, etc.):

```json
{
  "alerts": [
    {"rule": "wan_latency gt 100", "value": 125.3, "message": "WAN latency 125.3ms", "ts": 1234567890}
  ],
  "source": "unifi-monitor",
  "timestamp": 1234567890
}
```

## Configuration

All settings via environment variables (`.env` or `docker-compose.yml`):

| Variable | Default | Description |
|----------|---------|-------------|
| `UNIFI_HOST` | `192.168.1.1` | Gateway IP or hostname |
| `UNIFI_USERNAME` | `admin` | Local admin username |
| `UNIFI_PASSWORD` | *(required)* | Local admin password |
| `UNIFI_SITE` | `default` | UniFi site name (single site) |
| `UNIFI_SITES` | *(empty)* | Comma-separated site names for multi-site (overrides `UNIFI_SITE`) |
| `UNIFI_PORT` | `443` | Gateway HTTPS port |
| `WEB_HOST` | `0.0.0.0` | Dashboard bind address |
| `WEB_PORT` | `8080` | Dashboard port |
| `AUTH_USERNAME` | *(empty)* | HTTP Basic Auth username (both required to enable) |
| `AUTH_PASSWORD` | *(empty)* | HTTP Basic Auth password |
| `NETFLOW_ENABLED` | `true` | Enable NetFlow/IPFIX collector |
| `NETFLOW_HOST` | `0.0.0.0` | NetFlow listener bind address |
| `NETFLOW_PORT` | `2055` | NetFlow listener port |
| `POLL_INTERVAL` | `30` | Seconds between API polls (min 5) |
| `RETENTION_HOURS` | `168` | Data retention in hours (7 days) |
| `DB_PATH` | `data/monitor.db` | SQLite database path |
| `ALERT_WEBHOOK_URL` | *(empty)* | Webhook URL for alert notifications |
| `ALERT_COOLDOWN` | `300` | Seconds between repeated alerts per rule |

## API Reference

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check (uptime, DB stats) |
| `GET /api/overview` | Dashboard summary (health score, WAN, clients, devices, alarms) |
| `GET /api/clients?offset=0&limit=50` | Connected clients (paginated) |
| `GET /api/clients/{mac}/history?hours=24` | Client signal/satisfaction history |
| `GET /api/devices` | Adopted devices with stats |
| `GET /api/wan/history?hours=24` | WAN latency/status history |
| `GET /api/traffic/top-talkers?hours=1&limit=20` | Top source IPs by bytes |
| `GET /api/traffic/top-destinations?hours=1&limit=20` | Top destination IPs |
| `GET /api/traffic/top-ports?hours=1&limit=20` | Top ports by bytes |
| `GET /api/traffic/bandwidth?hours=24&bucket_minutes=5` | Bandwidth timeseries |
| `GET /api/traffic/dns-queries?hours=1&limit=100` | DNS query aggregates (per-client-per-server) |
| `GET /api/traffic/dns-top-clients?hours=1&limit=20` | Top DNS-querying clients |
| `GET /api/traffic/dns-top-servers?hours=1&limit=20` | Top DNS servers |
| `GET /api/compare?metric=latency&hours=24&offset_hours=168` | Historical comparison (latency/bandwidth/client_count) |
| `GET /api/sites` | Configured site list and default |
| `GET /api/alarms` | Active (non-archived) alarms |
| `GET /api/export/clients?hours=24&format=json&limit=10000` | Export client data (JSON or CSV) |
| `GET /api/export/wan?hours=24&format=json&limit=10000` | Export WAN metrics (JSON or CSV) |
| `GET /api/auth/token` | Get WebSocket auth token (requires Basic Auth) |
| `WS /api/ws` | WebSocket for live dashboard updates |

## NetFlow Setup

To see traffic data (top talkers, bandwidth charts), enable NetFlow/IPFIX on your UniFi gateway:

1. UniFi Network UI > Settings > System > NetFlow
2. Server: your machine's IP (where UniFi Monitor runs)
3. Port: 2055

Without NetFlow, the dashboard still shows client/device/WAN data from the UniFi API.

## Local Development

```bash
pip install -e ".[dev,netflow]"
cp .env.example .env
# Edit .env
python -m unifi_monitor
```

```bash
make test       # Run tests
make lint       # Ruff lint check
make format     # Auto-format with ruff
make check      # Lint + format check
```

## Compatibility

Works with any UniFi OS gateway: UCG-Max, UCG-Ultra, UDM, UDM-Pro, UDM-SE, UDR, Cloud Key Gen2+.

Requires local network access to the gateway (not cloud-only).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT
