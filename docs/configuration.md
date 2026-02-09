# Configuration

All settings are configured via environment variables. Use a `.env` file or pass them directly in `docker-compose.yml`.

## Environment Variables

### UniFi Gateway

| Variable | Default | Description |
|----------|---------|-------------|
| `UNIFI_HOST` | `192.168.1.1` | Gateway IP or hostname |
| `UNIFI_USERNAME` | `admin` | Local admin username |
| `UNIFI_PASSWORD` | *(required)* | Local admin password |
| `UNIFI_SITE` | `default` | UniFi site name (single site) |
| `UNIFI_SITES` | *(empty)* | Comma-separated site names for multi-site (overrides `UNIFI_SITE`) |
| `UNIFI_PORT` | `443` | Gateway HTTPS port |

### Web Dashboard

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_HOST` | `0.0.0.0` | Dashboard bind address |
| `WEB_PORT` | `8080` | Dashboard port |

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_USERNAME` | *(empty)* | HTTP Basic Auth username (both required to enable) |
| `AUTH_PASSWORD` | *(empty)* | HTTP Basic Auth password |

When both `AUTH_USERNAME` and `AUTH_PASSWORD` are set, all endpoints require HTTP Basic Auth except `/api/health` (bypassed for Docker healthchecks).

WebSocket authentication uses an hour-based SHA-256 token from `GET /api/auth/token`.

### NetFlow/IPFIX

| Variable | Default | Description |
|----------|---------|-------------|
| `NETFLOW_ENABLED` | `true` | Enable NetFlow/IPFIX collector |
| `NETFLOW_HOST` | `0.0.0.0` | NetFlow listener bind address |
| `NETFLOW_PORT` | `2055` | NetFlow listener port |

### Data

| Variable | Default | Description |
|----------|---------|-------------|
| `POLL_INTERVAL` | `30` | Seconds between API polls (min 5) |
| `RETENTION_HOURS` | `168` | Data retention in hours (default 7 days, min 1) |
| `DB_PATH` | `data/monitor.db` | SQLite database path |

### Alerts

| Variable | Default | Description |
|----------|---------|-------------|
| `ALERT_WEBHOOK_URL` | *(empty)* | Webhook URL for alert notifications (empty = disabled) |
| `ALERT_COOLDOWN` | `300` | Seconds between repeated alerts per rule (min 30) |

## .env.example

```bash
# UniFi Gateway
UNIFI_HOST=192.168.1.1
UNIFI_USERNAME=admin
UNIFI_PASSWORD=your_password_here
UNIFI_SITE=default
# UNIFI_SITES=default,office    # Multi-site (overrides UNIFI_SITE)
UNIFI_PORT=443

# Web Dashboard
WEB_HOST=0.0.0.0
WEB_PORT=8080

# Authentication (both required to enable)
AUTH_USERNAME=
AUTH_PASSWORD=

# NetFlow/IPFIX Collector
NETFLOW_ENABLED=true
NETFLOW_HOST=0.0.0.0
NETFLOW_PORT=2055

# Data
POLL_INTERVAL=30
RETENTION_HOURS=168
DB_PATH=data/monitor.db

# Alerts
ALERT_WEBHOOK_URL=
ALERT_COOLDOWN=300
```

## Multi-Site Setup

To monitor multiple UniFi sites:

1. Set `UNIFI_SITES` to a comma-separated list of site names:
   ```
   UNIFI_SITES=default,office,warehouse
   ```
2. The poller queries each site independently per cycle
3. All data is tagged with the `site` column in SQLite
4. The dashboard shows a site selector dropdown
5. API endpoints accept an optional `?site=` query parameter

`UNIFI_SITES` overrides `UNIFI_SITE` when set. If neither is set, defaults to `default`.

## Validation

All numeric values have bounds checking:

- `POLL_INTERVAL`: minimum 5 seconds
- `RETENTION_HOURS`: minimum 1 hour
- `ALERT_COOLDOWN`: minimum 30 seconds
- `UNIFI_PORT`: 1-65535

Invalid values log a warning and fall back to defaults.
