# UniFi Monitor

Real-time network monitoring dashboard for UniFi networks. One container, zero external dependencies beyond your gateway.

## Features

- **Live dashboard** -- health score, connected clients, WAN latency, device status, active alarms
- **WebSocket updates** -- instant push when poller completes (no polling lag)
- **Per-client drill-down** -- 24h signal strength and satisfaction charts per client
- **Alert notifications** -- configurable thresholds with webhook delivery (Discord, Slack, ntfy)
- **NetFlow/IPFIX visualization** -- top talkers, bandwidth over time, port/protocol breakdown
- **DNS traffic analysis** -- top DNS clients and servers from NetFlow data (port 53/853)
- **Multi-site support** -- monitor multiple UniFi sites with site selector dropdown
- **Historical comparison** -- compare latency, bandwidth, or client count vs last week
- **Data export** -- download client or WAN data as CSV or JSON
- **Dark/light theme** -- persisted in browser
- **Zero dependencies** -- no Grafana, no InfluxDB, no external database. SQLite + one container.

## Quick Start

### Docker (recommended)

```bash
git clone https://github.com/Matt-Bloise/unifi-monitor.git
cd unifi-monitor
cp .env.example .env
# Edit .env: set UNIFI_HOST, UNIFI_USERNAME, UNIFI_PASSWORD
docker compose up -d
```

Dashboard at **http://localhost:8080**.

### Local

```bash
pip install -e ".[dev,netflow]"
cp .env.example .env
# Edit .env
python -m unifi_monitor
```

## Pages

| Page | Description |
|------|-------------|
| [Architecture](architecture.md) | System design, data flow, SQLite schema, module overview |
| [Configuration](configuration.md) | Environment variables, `.env` reference, multi-site setup |
| [API Reference](api-reference.md) | All 19 REST endpoints + WebSocket protocol |
| [NetFlow](netflow.md) | NetFlow/IPFIX setup, DNS traffic analysis, gateway configuration |
| [Alerts](alerts.md) | Default rules, webhook payload format, custom rules, cooldowns |
| [Deployment](deployment.md) | Docker compose, systemd, reverse proxy, healthcheck |

## Compatibility

Works with any UniFi OS gateway: UCG-Max, UCG-Ultra, UDM, UDM-Pro, UDM-SE, UDR, Cloud Key Gen2+.

Requires local network access to the gateway (not cloud-only).
