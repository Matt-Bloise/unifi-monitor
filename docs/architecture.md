# Architecture

## System Overview

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

## Data Flow

1. **Poller** (`poller.py`) queries the UniFi gateway API every `POLL_INTERVAL` seconds
2. Responses are parsed into typed dicts and written to **SQLite** (`db.py`) with WAL mode
3. After each poll, the poller broadcasts a snapshot to all **WebSocket** clients (`ws.py`)
4. The poller evaluates **alert rules** (`alerts.py`) against the latest snapshot
5. If any rule fires (and is not in cooldown), a webhook POST is sent to `ALERT_WEBHOOK_URL`
6. **NetFlow collector** (`netflow/collector.py`) listens on UDP 2055 for IPFIX/NetFlow packets
7. Flow records are parsed (`netflow/parser.py`) and batch-written to SQLite every 10 seconds
8. **FastAPI** (`app.py`, `api/routes.py`) serves the REST API, WebSocket endpoint, and static dashboard

## Modules

| Module | Lines | Purpose |
|--------|-------|---------|
| `app.py` | 176 | FastAPI application with lifespan, auth middleware, static file serving |
| `config.py` | 78 | Environment variable loading with bounds validation |
| `db.py` | 527 | SQLite storage: schema, CRUD, retention cleanup, historical comparison |
| `poller.py` | 278 | Periodic UniFi API polling, per-endpoint error isolation, snapshot building |
| `unifi_client.py` | 124 | UniFi OS API wrapper: session reuse, CSRF, 401 auto-retry |
| `ws.py` | 39 | WebSocket broadcast hub (in-memory connection set) |
| `alerts.py` | 138 | Alert rule evaluation + webhook notification with per-rule cooldowns |
| `api/routes.py` | 434 | 18 REST endpoints + 1 WebSocket, dependency injection via `app.state` |
| `netflow/parser.py` | 133 | IPFIX v10 + NetFlow v5/v9 parser with template cache |
| `netflow/collector.py` | 85 | Async UDP listener, thread-safe batch writes |

## SQLite Schema

All tables include a `site` column (default `'default'`) for multi-site support. WAL mode enables concurrent reads during writes.

### wan_metrics

| Column | Type | Description |
|--------|------|-------------|
| ts | REAL | Unix timestamp |
| status | TEXT | `"ok"` or error string |
| latency_ms | REAL | Gateway-reported WAN latency |
| download_bps | REAL | Download speed in bits/sec |
| upload_bps | REAL | Upload speed in bits/sec |
| wan_ip | TEXT | Public IP address |
| cpu_pct | REAL | Gateway CPU percentage |
| mem_pct | REAL | Gateway memory percentage |
| site | TEXT | Site identifier |

### devices

| Column | Type | Description |
|--------|------|-------------|
| ts | REAL | Unix timestamp |
| mac | TEXT | Device MAC address |
| name | TEXT | Device name |
| model | TEXT | Hardware model |
| ip | TEXT | Device IP |
| state | INTEGER | 1 = online |
| cpu_pct | REAL | CPU percentage |
| mem_pct | REAL | Memory percentage |
| num_clients | INTEGER | Connected client count |
| satisfaction | INTEGER | Device satisfaction score |
| tx_bytes_r | REAL | Transmit rate (bytes/sec) |
| rx_bytes_r | REAL | Receive rate (bytes/sec) |
| site | TEXT | Site identifier |

### clients

| Column | Type | Description |
|--------|------|-------------|
| ts | REAL | Unix timestamp |
| mac | TEXT | Client MAC address |
| hostname | TEXT | Client hostname |
| ip | TEXT | Client IP |
| is_wired | INTEGER | 1 = wired, 0 = wireless |
| ssid | TEXT | Connected SSID |
| signal_dbm | INTEGER | Signal strength in dBm |
| satisfaction | INTEGER | Client satisfaction score |
| channel | INTEGER | Radio channel |
| radio | TEXT | Radio band (e.g., `na`, `ng`) |
| tx_bytes | REAL | Transmit bytes |
| rx_bytes | REAL | Receive bytes |
| tx_rate | REAL | Transmit rate (Mbps) |
| rx_rate | REAL | Receive rate (Mbps) |
| site | TEXT | Site identifier |

### netflow

| Column | Type | Description |
|--------|------|-------------|
| ts | REAL | Unix timestamp |
| src_ip | TEXT | Source IP address |
| dst_ip | TEXT | Destination IP address |
| src_port | INTEGER | Source port |
| dst_port | INTEGER | Destination port |
| protocol | INTEGER | IP protocol number |
| bytes | INTEGER | Total bytes in flow |
| packets | INTEGER | Total packets in flow |
| site | TEXT | Site identifier |

### alarms

| Column | Type | Description |
|--------|------|-------------|
| ts | REAL | Unix timestamp |
| alarm_id | TEXT | UniFi alarm ID |
| type | TEXT | Alarm type string |
| message | TEXT | Alarm message |
| device_name | TEXT | Originating device |
| archived | INTEGER | 1 = archived |
| site | TEXT | Site identifier |

## Design Decisions

- **SQLite over InfluxDB/Prometheus**: Single-network monitoring doesn't need time-series database overhead. SQLite WAL mode handles concurrent reads/writes.
- **No config files**: Environment variables only, Docker-native.
- **Custom IPFIX parser**: UCG-Max sends mixed template/data packets in the same UDP datagram. The standard `netflow` library can't handle this -- the custom parser processes set-by-set.
- **Session reuse**: Single `UnifiClient` instance, re-auth only on 401 to avoid rate limiting.
- **In-memory WebSocket**: Single-process, no Redis/pub-sub needed.
- **Weighted health score**: WAN status (40%) + device health (30%) + alarm severity (30%).
