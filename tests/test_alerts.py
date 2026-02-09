# test_alerts.py -- Alert engine tests

from __future__ import annotations

import time

import pytest

from unifi_monitor.alerts import AlertEngine, AlertRule, _extract_metric


def _make_snapshot(
    wan_status: str = "ok",
    latency_ms: float | None = 15.0,
    health_score: int = 100,
    devices_total: int = 2,
    devices_online: int = 2,
    alarms: int = 0,
) -> dict:
    return {
        "type": "update",
        "overview": {
            "health_score": health_score,
            "health_factors": [],
            "wan": {
                "status": wan_status,
                "latency_ms": latency_ms,
                "wan_ip": "1.2.3.4",
                "cpu_pct": 30.0,
                "mem_pct": 80.0,
            },
            "devices": {"total": devices_total, "online": devices_online},
            "clients": {"total": 5, "wireless": 3, "wired": 2},
            "alarms": alarms,
            "timestamp": time.time(),
        },
        "clients": [],
        "devices": [],
        "alarms": [],
    }


class TestExtractMetric:
    def test_wan_status(self) -> None:
        snap = _make_snapshot(wan_status="ok")
        assert _extract_metric(snap, "wan_status") == "ok"

    def test_wan_latency(self) -> None:
        snap = _make_snapshot(latency_ms=25.5)
        assert _extract_metric(snap, "wan_latency") == 25.5

    def test_health_score(self) -> None:
        snap = _make_snapshot(health_score=85)
        assert _extract_metric(snap, "health_score") == 85

    def test_device_offline(self) -> None:
        snap = _make_snapshot(devices_total=3, devices_online=1)
        assert _extract_metric(snap, "device_offline") == 2

    def test_unknown_metric(self) -> None:
        snap = _make_snapshot()
        assert _extract_metric(snap, "unknown_metric") is None


class TestAlertEvaluation:
    def test_wan_down_fires(self) -> None:
        engine = AlertEngine(
            rules=[AlertRule("wan_status", "ne", "ok", "WAN is {value}", 0)],
        )
        snap = _make_snapshot(wan_status="down")
        fired = engine.evaluate(snap)
        assert len(fired) == 1
        assert "WAN is down" in fired[0]["message"]

    def test_wan_ok_does_not_fire(self) -> None:
        engine = AlertEngine(
            rules=[AlertRule("wan_status", "ne", "ok", "WAN is {value}", 0)],
        )
        snap = _make_snapshot(wan_status="ok")
        fired = engine.evaluate(snap)
        assert len(fired) == 0

    def test_health_score_threshold(self) -> None:
        engine = AlertEngine(
            rules=[AlertRule("health_score", "lt", 50, "Health at {value}", 0)],
        )
        snap = _make_snapshot(health_score=30)
        fired = engine.evaluate(snap)
        assert len(fired) == 1

    def test_health_score_above_threshold_no_fire(self) -> None:
        engine = AlertEngine(
            rules=[AlertRule("health_score", "lt", 50, "Health at {value}", 0)],
        )
        snap = _make_snapshot(health_score=80)
        assert len(engine.evaluate(snap)) == 0

    def test_cooldown_prevents_repeat(self) -> None:
        engine = AlertEngine(
            rules=[AlertRule("wan_status", "ne", "ok", "WAN down", 300)],
        )
        snap = _make_snapshot(wan_status="down")
        first = engine.evaluate(snap)
        assert len(first) == 1
        second = engine.evaluate(snap)
        assert len(second) == 0  # cooldown blocks

    def test_multiple_rules_independent(self) -> None:
        engine = AlertEngine(
            rules=[
                AlertRule("wan_status", "ne", "ok", "WAN is {value}", 0),
                AlertRule("health_score", "lt", 50, "Health at {value}", 0),
                AlertRule("device_offline", "gt", 0, "{value} offline", 0),
            ],
        )
        snap = _make_snapshot(wan_status="down", health_score=30, devices_total=2, devices_online=1)
        fired = engine.evaluate(snap)
        assert len(fired) == 3

    def test_high_latency_fires(self) -> None:
        engine = AlertEngine(
            rules=[AlertRule("wan_latency", "gt", 100, "Latency {value}ms", 0)],
        )
        snap = _make_snapshot(latency_ms=125.3)
        fired = engine.evaluate(snap)
        assert len(fired) == 1
        assert "125.3ms" in fired[0]["message"]

    def test_normal_latency_no_fire(self) -> None:
        engine = AlertEngine(
            rules=[AlertRule("wan_latency", "gt", 100, "Latency {value}ms", 0)],
        )
        snap = _make_snapshot(latency_ms=15.0)
        assert len(engine.evaluate(snap)) == 0


class TestDefaultRules:
    def test_default_rules_loaded(self) -> None:
        engine = AlertEngine()
        assert len(engine.rules) == 4

    def test_healthy_snapshot_no_alerts(self) -> None:
        engine = AlertEngine()
        snap = _make_snapshot()
        assert len(engine.evaluate(snap)) == 0


@pytest.mark.asyncio
async def test_notify_no_webhook() -> None:
    """notify() with no webhook_url should be a no-op."""
    engine = AlertEngine(webhook_url=None)
    await engine.notify([{"message": "test"}])  # Should not raise
