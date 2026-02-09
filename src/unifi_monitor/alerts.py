# alerts.py -- Configurable alert thresholds with webhook notifications
# Evaluates rules against poll snapshots. Generic webhook format (Discord, Slack, ntfy, etc).

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

log = logging.getLogger(__name__)

OPERATORS = {
    "gt": lambda v, t: v > t,
    "lt": lambda v, t: v < t,
    "eq": lambda v, t: v == t,
    "ne": lambda v, t: v != t,
}


@dataclass
class AlertRule:
    metric: str
    operator: str
    threshold: float | str
    message: str
    cooldown_s: int = 300

    @property
    def key(self) -> str:
        return f"{self.metric}_{self.operator}_{self.threshold}"


DEFAULT_RULES = [
    AlertRule("wan_status", "ne", "ok", "WAN is {value}", 300),
    AlertRule("health_score", "lt", 50, "Health score dropped to {value}", 300),
    AlertRule("device_offline", "gt", 0, "{value} device(s) offline", 300),
    AlertRule("wan_latency", "gt", 100, "WAN latency {value}ms", 600),
]


def _extract_metric(snapshot: dict, metric: str) -> object | None:
    """Extract a metric value from the WS snapshot structure."""
    overview = snapshot.get("overview", {})
    wan = overview.get("wan", {})

    if metric == "wan_status":
        return wan.get("status")
    if metric == "wan_latency":
        return wan.get("latency_ms")
    if metric == "health_score":
        return overview.get("health_score")
    if metric == "device_offline":
        devices = overview.get("devices", {})
        total = devices.get("total", 0)
        online = devices.get("online", 0)
        return total - online
    if metric == "client_signal":
        # Min signal across all wireless clients
        clients = snapshot.get("clients", [])
        signals = [c.get("signal_dbm") for c in clients if c.get("signal_dbm") is not None]
        return min(signals) if signals else None
    return None


@dataclass
class AlertEngine:
    rules: list[AlertRule] = field(default_factory=lambda: list(DEFAULT_RULES))
    webhook_url: str | None = None
    _cooldowns: dict[str, float] = field(default_factory=dict)

    def evaluate(self, snapshot: dict) -> list[dict]:
        """Evaluate all rules against a snapshot. Returns list of fired alerts."""
        fired: list[dict] = []
        now = time.time()

        for rule in self.rules:
            value = _extract_metric(snapshot, rule.metric)
            if value is None:
                continue

            op_fn = OPERATORS.get(rule.operator)
            if op_fn is None:
                continue

            try:
                if isinstance(rule.threshold, type(value)):
                    threshold = rule.threshold
                else:
                    threshold = type(value)(rule.threshold)
                if not op_fn(value, threshold):
                    continue
            except (ValueError, TypeError):
                continue

            # Check cooldown
            last_fired = self._cooldowns.get(rule.key, 0)
            if now - last_fired < rule.cooldown_s:
                continue

            self._cooldowns[rule.key] = now
            fired.append({
                "rule": f"{rule.metric} {rule.operator} {rule.threshold}",
                "value": value,
                "message": rule.message.format(
                    value=value, metric=rule.metric, threshold=rule.threshold,
                ),
                "ts": now,
            })

        return fired

    async def notify(self, alerts: list[dict]) -> None:
        """POST fired alerts to webhook URL."""
        if not self.webhook_url or not alerts:
            return

        payload = {
            "alerts": alerts,
            "source": "unifi-monitor",
            "timestamp": time.time(),
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.webhook_url, json=payload)
                if resp.status_code >= 400:
                    log.warning("Alert webhook returned %d: %s", resp.status_code, resp.text[:200])
                else:
                    log.info("Alert webhook sent (%d alerts)", len(alerts))
        except Exception as e:
            log.warning("Alert webhook failed: %s", e)
