# netflow

IPFIX/NetFlow UDP collector and parser for traffic analysis.

## Modules

| Module | Lines | Purpose |
|--------|-------|---------|
| `parser.py` | 133 | IPFIX v10, NetFlow v5/v9 parser with template cache management |
| `collector.py` | 85 | Async UDP listener on port 2055, thread-safe batch writes every 10s |
| `__init__.py` | - | Package marker |

## Protocol Support

| Protocol | Version | Notes |
|----------|---------|-------|
| IPFIX | v10 | Recommended. Set-by-set parsing for UCG-Max compatibility |
| NetFlow | v9 | Full support with template caching |
| NetFlow | v5 | Fixed-format, no templates needed |

## UCG-Max Compatibility

The UCG-Max sends mixed template and data sets within a single UDP datagram. The standard `netflow` Python library parses entire packets as one type, which fails on these mixed packets. The custom parser in `parser.py` processes each set independently:

1. Read the packet header (version, count, length)
2. Iterate through sets by set ID:
   - Set ID 2 (IPFIX template): cache the template
   - Set ID 3 (IPFIX options template): skip
   - Set ID >= 256 (IPFIX data): decode using cached template
3. Extract fields: `src_ip`, `dst_ip`, `src_port`, `dst_port`, `protocol`, `bytes`, `packets`

Templates are cached in memory and persist until the collector restarts.

## Data Pipeline

```
Gateway (UDP) ──> collector.py (asyncio UDP listener)
                      │
                      ├── parser.py (decode IPFIX/NFv5/NFv9)
                      ├── Buffer in thread-safe list
                      │
                      └── Flush to SQLite every 10 seconds (batch INSERT)
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NETFLOW_ENABLED` | `true` | Enable/disable |
| `NETFLOW_HOST` | `0.0.0.0` | Bind address |
| `NETFLOW_PORT` | `2055` | UDP port |

## Optional Dependency

NetFlow support requires the `netflow` package:

```bash
pip install -e ".[netflow]"
```

If `netflow` is not installed, the collector logs a warning and does not start.
