# API Reference

All endpoints are served at `http://<host>:8080`. When Basic Auth is enabled, all endpoints except `/api/health` require authentication.

All endpoints accept an optional `?site=` query parameter for multi-site filtering.

## Health

### `GET /api/health`

Health check endpoint. Bypasses authentication for Docker healthchecks.

**Response:**

```json
{
  "status": "ok",
  "uptime_s": 3600.5,
  "last_write_ts": 1234567890.123,
  "db_size_bytes": 2310144
}
```

## Authentication

### `GET /api/auth/token`

Returns a WebSocket authentication token (hour-based SHA-256 hash). Only available when Basic Auth is enabled.

**Response:**

```json
{
  "token": "a1b2c3d4..."
}
```

## Sites

### `GET /api/sites`

List configured sites and the default site.

**Response:**

```json
{
  "sites": ["default", "office"],
  "default": "default"
}
```

## Dashboard

### `GET /api/overview`

Dashboard summary with health score, WAN status, client/device counts, and alarms.

**Response:**

```json
{
  "health_score": 92,
  "wan": {
    "status": "ok",
    "latency_ms": 12.5,
    "wan_ip": "45.47.143.169",
    "cpu_pct": 30.2,
    "mem_pct": 80.1
  },
  "client_count": 24,
  "device_count": 2,
  "alarm_count": 0,
  "ts": 1234567890.123
}
```

Health score is weighted: WAN status (40%) + device health (30%) + alarm severity (30%).

## Clients

### `GET /api/clients`

Connected clients, paginated.

| Param | Default | Description |
|-------|---------|-------------|
| `offset` | `0` | Pagination offset |
| `limit` | `50` | Page size |

**Response:**

```json
{
  "clients": [
    {
      "mac": "aa:bb:cc:dd:ee:ff",
      "hostname": "MacBook-Pro",
      "ip": "192.168.1.100",
      "is_wired": false,
      "ssid": "__5G__",
      "signal_dbm": -45,
      "satisfaction": 98,
      "channel": 100,
      "radio": "na",
      "tx_bytes": 1234567,
      "rx_bytes": 7654321,
      "tx_rate": 1200.0,
      "rx_rate": 1200.0
    }
  ],
  "total": 24,
  "ts": 1234567890.123
}
```

### `GET /api/clients/{mac}/history`

Signal strength and satisfaction history for a specific client.

| Param | Default | Description |
|-------|---------|-------------|
| `hours` | `24` | Lookback window |

**Response:**

```json
{
  "mac": "aa:bb:cc:dd:ee:ff",
  "history": [
    {"ts": 1234567890, "signal_dbm": -45, "satisfaction": 98}
  ]
}
```

## Devices

### `GET /api/devices`

Adopted devices with stats.

**Response:**

```json
{
  "devices": [
    {
      "mac": "0c:ea:14:39:e8:31",
      "name": "UCG-Max",
      "model": "UCG-Max",
      "ip": "192.168.1.1",
      "state": 1,
      "cpu_pct": 30.2,
      "mem_pct": 80.1,
      "num_clients": 24,
      "satisfaction": 95,
      "tx_bytes_r": 50000.0,
      "rx_bytes_r": 200000.0
    }
  ],
  "ts": 1234567890.123
}
```

## WAN

### `GET /api/wan/history`

WAN latency and status history.

| Param | Default | Description |
|-------|---------|-------------|
| `hours` | `24` | Lookback window |

**Response:**

```json
{
  "history": [
    {
      "ts": 1234567890,
      "status": "ok",
      "latency_ms": 12.5,
      "download_bps": 600000000,
      "upload_bps": 50000000,
      "wan_ip": "45.47.143.169",
      "cpu_pct": 30.2,
      "mem_pct": 80.1
    }
  ]
}
```

## Traffic (NetFlow)

Requires NetFlow/IPFIX to be enabled and sending data.

### `GET /api/traffic/top-talkers`

Top source IPs by total bytes.

| Param | Default | Description |
|-------|---------|-------------|
| `hours` | `1` | Lookback window |
| `limit` | `20` | Max results |

### `GET /api/traffic/top-destinations`

Top destination IPs by total bytes. Same params as top-talkers.

### `GET /api/traffic/top-ports`

Top ports by total bytes. Same params as top-talkers.

### `GET /api/traffic/bandwidth`

Bandwidth timeseries, bucketed.

| Param | Default | Description |
|-------|---------|-------------|
| `hours` | `24` | Lookback window |
| `bucket_minutes` | `5` | Bucket size in minutes |

**Response:**

```json
{
  "buckets": [
    {"ts": 1234567890, "bytes": 50000000}
  ]
}
```

### `GET /api/traffic/dns-queries`

DNS query aggregates (per-client-per-server).

| Param | Default | Description |
|-------|---------|-------------|
| `hours` | `1` | Lookback window |
| `limit` | `100` | Max results |

### `GET /api/traffic/dns-top-clients`

Top DNS-querying clients by total bytes.

| Param | Default | Description |
|-------|---------|-------------|
| `hours` | `1` | Lookback window |
| `limit` | `20` | Max results |

### `GET /api/traffic/dns-top-servers`

Top DNS servers by total bytes. Same params as dns-top-clients.

## Comparison

### `GET /api/compare`

Historical comparison (current period vs offset period).

| Param | Default | Description |
|-------|---------|-------------|
| `metric` | *(required)* | `latency`, `bandwidth`, or `client_count` |
| `hours` | `24` | Window size |
| `offset_hours` | `168` | Offset to comparison period (default: 1 week) |

**Response:**

```json
{
  "current": [{"ts": 1234567890, "value": 12.5}],
  "previous": [{"ts": 1234567890, "value": 14.2}]
}
```

## Alarms

### `GET /api/alarms`

Active (non-archived) alarms from the UniFi gateway.

**Response:**

```json
{
  "alarms": [
    {
      "alarm_id": "abc123",
      "type": "EVT_GW_WANTransition",
      "message": "WAN transitioned",
      "device_name": "UCG-Max",
      "ts": 1234567890
    }
  ]
}
```

## Export

### `GET /api/export/clients`

Export client data as JSON or CSV.

| Param | Default | Description |
|-------|---------|-------------|
| `hours` | `24` | Lookback window |
| `format` | `json` | `json` or `csv` |
| `limit` | `10000` | Max rows |

### `GET /api/export/wan`

Export WAN metrics as JSON or CSV. Same params as export/clients.

## WebSocket

### `WS /api/ws`

Live dashboard updates. When the poller completes a cycle, it broadcasts the latest snapshot to all connected clients.

**Connection:**

```
ws://localhost:8080/api/ws
```

When Basic Auth is enabled, include the token:

```
ws://localhost:8080/api/ws?token=<token_from_auth_endpoint>
```

**Messages (server -> client):**

JSON objects matching the `/api/overview` response shape, sent after each poll cycle.

**Behavior:**

- Server sends data immediately after each poller cycle
- No client-to-server messages expected
- Dead connections are automatically cleaned up
- Dashboard JS auto-reconnects with exponential backoff (1s -> 30s max)
- Falls back to REST polling after 3 consecutive WebSocket failures
