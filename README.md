# UniFi Monitor

Real-time network monitoring dashboard for UniFi networks. One command to deploy, zero configuration beyond gateway credentials.

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)

## What It Does

- **Live dashboard** -- health score, connected clients, WAN latency, device status
- **NetFlow/IPFIX visualization** -- top talkers, bandwidth over time, port/protocol breakdown
- **Client monitoring** -- signal strength, satisfaction scores, per-client bandwidth
- **WAN tracking** -- latency history, status changes, gateway CPU/memory
- **Zero dependencies** -- no Grafana, no InfluxDB, no external database. SQLite + one container.

## Quick Start

### Docker (recommended)

```bash
git clone https://github.com/matt-bloise/unifi-monitor.git
cd unifi-monitor
cp .env.example .env
# Edit .env: set UNIFI_HOST, UNIFI_USERNAME, UNIFI_PASSWORD
docker compose up -d
```

Dashboard at **http://localhost:8080**.

### Python

```bash
pip install -e .
cp .env.example .env
# Edit .env
python -m unifi_monitor
```

## NetFlow Setup

To see traffic data (top talkers, bandwidth charts), enable NetFlow/IPFIX on your UniFi gateway:

1. UniFi Network UI > Settings > System > NetFlow
2. Server: your machine's IP (where UniFi Monitor runs)
3. Port: 2055

Without NetFlow, the dashboard still shows client/device/WAN data from the UniFi API.

## Configuration

All settings are environment variables (set in `.env` or `docker-compose.yml`):

| Variable | Default | Description |
|----------|---------|-------------|
| `UNIFI_HOST` | `192.168.1.1` | Gateway IP |
| `UNIFI_USERNAME` | `admin` | Local admin username |
| `UNIFI_PASSWORD` | *(required)* | Local admin password |
| `UNIFI_SITE` | `default` | UniFi site name |
| `WEB_PORT` | `8080` | Dashboard port |
| `NETFLOW_ENABLED` | `true` | Enable NetFlow/IPFIX collector |
| `NETFLOW_PORT` | `2055` | NetFlow listener port |
| `POLL_INTERVAL` | `30` | Seconds between API polls |
| `RETENTION_HOURS` | `168` | Data retention (7 days default) |

## Compatibility

Works with any UniFi OS gateway:
- UCG-Max, UCG-Ultra
- UDM, UDM-Pro, UDM-SE
- UDR
- Cloud Key Gen2+

Requires local network access to the gateway (not cloud-only).

## Architecture

Single container, single process:

```
┌─────────────────────────────────────┐
│         unifi-monitor               │
│                                     │
│  ┌──────────┐    ┌───────────────┐  │
│  │  Poller   │───>│   SQLite DB   │  │
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

- **Poller**: Hits UniFi API every 30s for device/client/WAN data
- **NetFlow Collector**: Async UDP listener for IPFIX/NetFlow traffic data
- **SQLite**: WAL mode for concurrent reads/writes, auto-cleanup by retention policy
- **FastAPI**: REST API + serves the static dashboard

No external databases, no message queues, no complexity.

## Development

```bash
pip install -e ".[dev]"
make test
make lint
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for architecture details and how to add features.

## License

MIT
