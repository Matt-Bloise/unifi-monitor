# Alerts

UniFi Monitor evaluates alert rules after each poller cycle and sends webhook notifications when thresholds are exceeded.

## Setup

Set `ALERT_WEBHOOK_URL` to enable:

```bash
ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

Works with Discord webhooks, Slack incoming webhooks, ntfy, or any HTTP endpoint that accepts JSON POST.

## Default Rules

| Metric | Operator | Threshold | Message | Cooldown |
|--------|----------|-----------|---------|----------|
| `wan_status` | `ne` (not equal) | `ok` | "WAN is {value}" | 300s |
| `health_score` | `lt` (less than) | `50` | "Health score dropped to {value}" | 300s |
| `device_offline` | `gt` (greater than) | `0` | "{value} device(s) offline" | 300s |
| `wan_latency` | `gt` (greater than) | `100` | "WAN latency {value}ms" | 600s |

## Webhook Payload

When one or more rules fire, a single POST is sent:

```json
{
  "alerts": [
    {
      "rule": "wan_latency gt 100",
      "value": 125.3,
      "message": "WAN latency 125.3ms",
      "ts": 1234567890
    }
  ],
  "source": "unifi-monitor",
  "timestamp": 1234567890
}
```

Multiple alerts can fire in the same cycle and are batched into one webhook call.

## Cooldowns

Each rule has an independent cooldown timer. After firing, the rule won't fire again until the cooldown expires. This prevents notification spam during sustained issues.

| Variable | Default | Min | Description |
|----------|---------|-----|-------------|
| `ALERT_COOLDOWN` | `300` | `30` | Seconds between repeated alerts per rule |

The default cooldown is 5 minutes. The `wan_latency` rule uses a 10-minute cooldown to reduce noise from transient latency spikes.

## Metric Extraction

Metrics are extracted from the poller snapshot:

| Metric | Source | Type |
|--------|--------|------|
| `wan_status` | WAN status string | string |
| `health_score` | Calculated weighted score | integer (0-100) |
| `device_offline` | Count of devices with state != 1 | integer |
| `wan_latency` | Gateway-reported WAN latency | float (ms) |

## Custom Rules

Alert rules are defined in `alerts.py`. To add a custom rule, add an entry to the `DEFAULT_RULES` list:

```python
{
    "metric": "mem_pct",
    "op": "gt",
    "threshold": 95,
    "message": "Gateway memory at {value}%",
    "cooldown": 600,
}
```

Supported operators: `gt`, `lt`, `ge`, `le`, `eq`, `ne`.
