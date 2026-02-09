# NetFlow / IPFIX

UniFi Monitor includes a built-in NetFlow/IPFIX collector that provides traffic visibility beyond what the UniFi API offers: top talkers, bandwidth over time, port/protocol breakdown, and DNS traffic analysis.

## What NetFlow Provides

Without NetFlow, the dashboard shows client/device/WAN data from the UniFi API. With NetFlow enabled, you also get:

- **Top talkers** -- source and destination IPs ranked by bytes
- **Top ports** -- which ports/protocols consume the most bandwidth
- **Bandwidth timeseries** -- traffic volume over time with configurable bucket size
- **DNS traffic analysis** -- top DNS clients, top DNS servers, per-client-per-server query aggregates

## Gateway Setup

Enable NetFlow/IPFIX on your UniFi gateway:

1. **UniFi Network UI** > Settings > System > NetFlow
2. **Server**: IP address of the machine running UniFi Monitor
3. **Port**: `2055` (default)
4. **Version**: IPFIX (v10) is preferred; v5 and v9 are also supported

The gateway will begin sending flow records as UDP datagrams to the configured address.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NETFLOW_ENABLED` | `true` | Enable/disable the collector |
| `NETFLOW_HOST` | `0.0.0.0` | Bind address for UDP listener |
| `NETFLOW_PORT` | `2055` | UDP port for flow data |

In Docker, port 2055/udp is exposed by default:

```yaml
ports:
  - "${NETFLOW_PORT:-2055}:2055/udp"
```

## Protocol Support

| Protocol | Version | Support |
|----------|---------|---------|
| IPFIX | v10 | Full (recommended) |
| NetFlow | v9 | Full |
| NetFlow | v5 | Full |

### UCG-Max Quirk

The UCG-Max sends mixed template and data sets within a single UDP datagram. The standard `netflow` Python library cannot handle this. UniFi Monitor includes a custom set-by-set parser (`netflow/parser.py`) that processes each set independently, caching templates as they arrive.

## Data Pipeline

```
Gateway ──UDP──> Collector (port 2055)
                    │
                    ├── Parse IPFIX/NetFlow sets
                    ├── Extract: src_ip, dst_ip, src_port, dst_port, protocol, bytes, packets
                    ├── Buffer in memory (thread-safe)
                    │
                    └── Batch write to SQLite every 10 seconds
```

## DNS Traffic Analysis

DNS queries are identified by destination port 53 (standard DNS) or 853 (DNS over TLS). The following endpoints aggregate DNS-related flow records:

| Endpoint | Description |
|----------|-------------|
| `GET /api/traffic/dns-queries` | Per-client-per-server query aggregates |
| `GET /api/traffic/dns-top-clients` | Top DNS-querying clients by bytes |
| `GET /api/traffic/dns-top-servers` | Top DNS servers by bytes |

This is useful for identifying which clients make the most DNS queries and which resolvers they use.

## API Endpoints

All traffic endpoints accept `?hours=` and `?limit=` parameters.

| Endpoint | Default hours | Default limit |
|----------|--------------|---------------|
| `/api/traffic/top-talkers` | 1 | 20 |
| `/api/traffic/top-destinations` | 1 | 20 |
| `/api/traffic/top-ports` | 1 | 20 |
| `/api/traffic/bandwidth` | 24 | N/A (bucketed) |
| `/api/traffic/dns-queries` | 1 | 100 |
| `/api/traffic/dns-top-clients` | 1 | 20 |
| `/api/traffic/dns-top-servers` | 1 | 20 |

## Troubleshooting

**No traffic data showing up:**

1. Verify NetFlow is enabled on the gateway (UI > Settings > System > NetFlow)
2. Verify the server IP matches the machine running UniFi Monitor
3. Check that port 2055/udp is not blocked by a firewall
4. In Docker, ensure the UDP port is mapped: `2055:2055/udp`
5. Check logs for `NetFlow collector started` at startup

**Template errors:**

The first few packets after a gateway restart may be data-only (no templates). The parser discards these and waits for template sets to arrive. This is normal and resolves within a few seconds.
