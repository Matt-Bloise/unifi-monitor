# UniFi Monitor

Real-time network monitoring dashboard for UniFi networks. One container, zero external dependencies beyond your gateway.

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)

<!-- Screenshot placeholder: replace with actual dashboard screenshot -->
<!-- ![Dashboard](docs/screenshot.png) -->

## Quick Start

```bash
git clone https://github.com/matt-bloise/unifi-monitor.git
cd unifi-monitor
cp .env.example .env
# Edit .env: set UNIFI_HOST, UNIFI_USERNAME, UNIFI_PASSWORD
docker compose up -d
```

Dashboard at **http://localhost:8080**.

## Features

- **Live dashboard** -- health score, connected clients, WAN latency, device status, active alarms
- **NetFlow/IPFIX visualization** -- top talkers, bandwidth over time, port/protocol breakdown
- **Client monitoring** -- signal strength, satisfaction scores, per-client bandwidth, sortable columns
- **WAN tracking** -- latency history, status changes, gateway CPU/memory
- **Device status** -- gateway + AP cards with online/offline badges
- **Stale data detection** -- yellow/red banners when connection drops
- **Auto-pause** -- stops polling when browser tab is hidden
- **Docker healthcheck** -- `/api/health` endpoint for monitoring
- **Zero dependencies** -- no Grafana, no InfluxDB, no external database. SQLite + one container.

## Architecture

```
┌─────────────────────────────────────┐
│         unifi-monitor               │
│                                     │
│  ┌──────────┐    ┌───────────────┐  │
│  │  Poller   │──>│   SQLite DB   │  │
│  │(UniFi API)│    │  (WAL mode)   │  │
│  └──────────┘    └──────┬────────┘  │
│                         │           │
│  ┌──────────┐           │           │
│  │ NetFlow  │───────────┘           │
│  │(UDP 2055)│                       │
│  └──────────┘    ┌──────┴────────┐  │
│                  │   FastAPI     │  │
│                  │  REST + Web   │──── :8080
│                  └───────────────┘  │
└─────────────────────────────────────┘
```

## Configuration

All settings via environment variables (`.env` or `docker-compose.yml`):

| Variable | Default | Description |
|----------|---------|-------------|
| `UNIFI_HOST` | `192.168.1.1` | Gateway IP or hostname |
| `UNIFI_USERNAME` | `admin` | Local admin username |
| `UNIFI_PASSWORD` | *(required)* | Local admin password |
| `UNIFI_SITE` | `default` | UniFi site name |
| `UNIFI_PORT` | `443` | Gateway HTTPS port |
| `WEB_HOST` | `0.0.0.0` | Dashboard bind address |
| `WEB_PORT` | `8080` | Dashboard port |
| `NETFLOW_ENABLED` | `true` | Enable NetFlow/IPFIX collector |
| `NETFLOW_PORT` | `2055` | NetFlow listener port |
| `POLL_INTERVAL` | `30` | Seconds between API polls (min 5) |
| `RETENTION_HOURS` | `168` | Data retention in hours (7 days) |
| `DB_PATH` | `data/monitor.db` | SQLite database path |

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
| `GET /api/alarms` | Active (non-archived) alarms |

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
