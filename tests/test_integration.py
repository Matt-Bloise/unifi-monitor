# test_integration.py -- Integration tests for full request/response cycles
# Tests multi-step workflows: data ingestion -> API query -> correct response.

from __future__ import annotations

import base64
import csv
import io
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from unifi_monitor.app import app
from unifi_monitor.config import config
from unifi_monitor.db import Database


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_db(tmp_path: Path) -> Database:
    """Empty database for integration tests."""
    return Database(tmp_path / "integration.db")


@pytest.fixture
def integration_client(fresh_db: Database) -> TestClient:
    """TestClient with a fresh empty DB and auth disabled."""
    app.state.db = fresh_db
    app.state.start_time = time.time()
    app.state.sites = ["default"]
    return TestClient(app)


def _basic_auth(user: str, password: str) -> dict:
    creds = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {creds}"}


# ---------------------------------------------------------------------------
# Full data lifecycle: write to DB, read via API, verify shapes
# ---------------------------------------------------------------------------


class TestDataLifecycle:
    """Ingest data into the DB, then verify every API endpoint returns it correctly."""

    def _seed(self, db: Database) -> float:
        ts = time.time()
        db.insert_wan(ts, "ok", 22.3, "203.0.113.1", 45.0, 62.0, 1_000_000.0, 500_000.0)
        db.insert_devices(
            ts,
            [
                {
                    "mac": "aa:bb:cc:00:00:01",
                    "name": "Gateway",
                    "model": "UCG-Max",
                    "ip": "192.168.1.1",
                    "state": 1,
                    "cpu_pct": 45.0,
                    "mem_pct": 62.0,
                    "num_clients": 5,
                    "satisfaction": 99,
                    "tx_bytes_r": 1200.0,
                    "rx_bytes_r": 3400.0,
                },
                {
                    "mac": "aa:bb:cc:00:00:02",
                    "name": "AP-LR",
                    "model": "U6-LR",
                    "ip": "192.168.1.2",
                    "state": 1,
                    "cpu_pct": 8.0,
                    "mem_pct": 35.0,
                    "num_clients": 12,
                    "satisfaction": 96,
                    "tx_bytes_r": 800.0,
                    "rx_bytes_r": 1500.0,
                },
            ],
        )
        db.insert_clients(
            ts,
            [
                {
                    "mac": "cc:dd:ee:00:00:01",
                    "hostname": "workstation",
                    "ip": "192.168.1.100",
                    "is_wired": True,
                    "ssid": None,
                    "signal_dbm": None,
                    "satisfaction": 100,
                    "channel": None,
                    "radio": None,
                    "tx_bytes": 20_000_000,
                    "rx_bytes": 80_000_000,
                    "tx_rate": None,
                    "rx_rate": None,
                },
                {
                    "mac": "cc:dd:ee:00:00:02",
                    "hostname": "iphone",
                    "ip": "192.168.1.101",
                    "is_wired": False,
                    "ssid": "HomeNet",
                    "signal_dbm": -48,
                    "satisfaction": 97,
                    "channel": 36,
                    "radio": "na",
                    "tx_bytes": 5_000_000,
                    "rx_bytes": 15_000_000,
                    "tx_rate": 866.0,
                    "rx_rate": 866.0,
                },
            ],
        )
        db.insert_netflow_batch(
            ts,
            [
                {
                    "src_ip": "192.168.1.100",
                    "dst_ip": "8.8.8.8",
                    "src_port": 40000,
                    "dst_port": 443,
                    "protocol": 6,
                    "bytes": 200_000,
                    "packets": 150,
                },
                {
                    "src_ip": "192.168.1.101",
                    "dst_ip": "1.1.1.1",
                    "src_port": 40001,
                    "dst_port": 53,
                    "protocol": 17,
                    "bytes": 2_000,
                    "packets": 10,
                },
                {
                    "src_ip": "192.168.1.100",
                    "dst_ip": "1.1.1.1",
                    "src_port": 40002,
                    "dst_port": 853,
                    "protocol": 6,
                    "bytes": 3_000,
                    "packets": 8,
                },
            ],
        )
        db.insert_alarms(
            ts,
            [
                {
                    "id": "alarm-int-1",
                    "type": "EVT_AP_Lost_Contact",
                    "message": "AP-LR lost contact",
                    "device_name": "AP-LR",
                    "archived": False,
                },
            ],
        )
        return ts

    def test_overview_reflects_seeded_data(self, fresh_db: Database, integration_client: TestClient):
        self._seed(fresh_db)
        resp = integration_client.get("/api/overview")
        assert resp.status_code == 200
        data = resp.json()

        assert data["devices"]["total"] == 2
        assert data["devices"]["online"] == 2
        assert data["clients"]["total"] == 2
        assert data["clients"]["wired"] == 1
        assert data["clients"]["wireless"] == 1
        assert data["wan"]["status"] == "ok"
        assert data["wan"]["latency_ms"] == 22.3
        assert data["wan"]["wan_ip"] == "203.0.113.1"
        assert data["alarms"] == 1
        assert 0 <= data["health_score"] <= 100

    def test_clients_sorted_by_rx_bytes(self, fresh_db: Database, integration_client: TestClient):
        self._seed(fresh_db)
        resp = integration_client.get("/api/clients")
        data = resp.json()
        assert data["total"] == 2
        clients = data["data"]
        # workstation has 80M rx, iphone has 15M -- workstation should be first
        assert clients[0]["hostname"] == "workstation"
        assert clients[1]["hostname"] == "iphone"

    def test_devices_all_present(self, fresh_db: Database, integration_client: TestClient):
        self._seed(fresh_db)
        resp = integration_client.get("/api/devices")
        data = resp.json()
        assert len(data) == 2
        names = {d["name"] for d in data}
        assert names == {"Gateway", "AP-LR"}

    def test_wan_history_returns_seeded_point(
        self, fresh_db: Database, integration_client: TestClient
    ):
        self._seed(fresh_db)
        resp = integration_client.get("/api/wan/history?hours=1")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["latency_ms"] == 22.3

    def test_alarms_returns_non_archived(self, fresh_db: Database, integration_client: TestClient):
        self._seed(fresh_db)
        resp = integration_client.get("/api/alarms")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["alarm_id"] == "alarm-int-1"

    def test_top_talkers_aggregation(self, fresh_db: Database, integration_client: TestClient):
        self._seed(fresh_db)
        resp = integration_client.get("/api/traffic/top-talkers?hours=1")
        data = resp.json()
        # Two src IPs: 192.168.1.100 (200k + 3k = 203k), 192.168.1.101 (2k)
        assert len(data) == 2
        assert data[0]["src_ip"] == "192.168.1.100"
        assert data[0]["total_bytes"] == 203_000

    def test_top_destinations_aggregation(self, fresh_db: Database, integration_client: TestClient):
        self._seed(fresh_db)
        resp = integration_client.get("/api/traffic/top-destinations?hours=1")
        data = resp.json()
        # 1.1.1.1 (2k + 3k = 5k), 8.8.8.8 (200k)
        assert data[0]["dst_ip"] == "8.8.8.8"
        assert data[0]["total_bytes"] == 200_000

    def test_dns_endpoints_use_netflow(self, fresh_db: Database, integration_client: TestClient):
        self._seed(fresh_db)
        # DNS queries: port 53 (UDP/17) and port 853 (TCP/6)
        resp = integration_client.get("/api/traffic/dns-queries?hours=1")
        data = resp.json()
        assert len(data) == 2  # two unique src_ip/dst_ip pairs on DNS ports

        resp = integration_client.get("/api/traffic/dns-top-clients?hours=1")
        data = resp.json()
        assert len(data) == 2

        resp = integration_client.get("/api/traffic/dns-top-servers?hours=1")
        data = resp.json()
        # Only 1.1.1.1 receives DNS traffic
        assert len(data) == 1
        assert data[0]["dst_ip"] == "1.1.1.1"

    def test_bandwidth_timeseries(self, fresh_db: Database, integration_client: TestClient):
        self._seed(fresh_db)
        resp = integration_client.get("/api/traffic/bandwidth?hours=1&bucket_minutes=60")
        data = resp.json()
        assert len(data) >= 1
        assert "mbps" in data[0]
        assert data[0]["total_bytes"] == 205_000  # 200k + 2k + 3k

    def test_client_history_tracks_over_time(
        self, fresh_db: Database, integration_client: TestClient
    ):
        ts1 = time.time() - 600
        ts2 = time.time()
        for ts in (ts1, ts2):
            fresh_db.insert_clients(
                ts,
                [
                    {
                        "mac": "cc:dd:ee:00:00:02",
                        "hostname": "iphone",
                        "ip": "192.168.1.101",
                        "is_wired": False,
                        "ssid": "HomeNet",
                        "signal_dbm": -48,
                        "satisfaction": 97,
                        "channel": 36,
                        "radio": "na",
                        "tx_bytes": 5_000_000,
                        "rx_bytes": 15_000_000,
                        "tx_rate": 866.0,
                        "rx_rate": 866.0,
                    },
                ],
            )
        resp = integration_client.get("/api/clients/cc:dd:ee:00:00:02/history?hours=1")
        data = resp.json()
        assert len(data) == 2

    def test_health_endpoint_reflects_db_stats(
        self, fresh_db: Database, integration_client: TestClient
    ):
        self._seed(fresh_db)
        resp = integration_client.get("/api/health")
        data = resp.json()
        assert data["status"] == "ok"
        assert data["db_size_bytes"] > 0
        assert data["last_write_ts"] > 0


# ---------------------------------------------------------------------------
# Multi-site integration: data isolation across sites
# ---------------------------------------------------------------------------


class TestMultiSiteIntegration:
    """Verify that the API correctly filters data by site query param."""

    @pytest.fixture
    def multisite_client(self, fresh_db: Database) -> TestClient:
        app.state.db = fresh_db
        app.state.start_time = time.time()
        app.state.sites = ["office", "warehouse"]

        ts = time.time()
        fresh_db.insert_wan(ts, "ok", 10.0, "10.0.0.1", 20.0, 50.0, site="office")
        fresh_db.insert_wan(ts, "ok", 30.0, "10.0.1.1", 60.0, 70.0, site="warehouse")
        fresh_db.insert_devices(
            ts,
            [{"mac": "aa:00:00:00:00:01", "name": "Office-GW", "state": 1}],
            site="office",
        )
        fresh_db.insert_devices(
            ts,
            [{"mac": "bb:00:00:00:00:01", "name": "WH-GW", "state": 1}],
            site="warehouse",
        )
        fresh_db.insert_clients(
            ts,
            [
                {
                    "mac": "cc:00:00:00:00:01",
                    "hostname": "office-pc",
                    "ip": "10.0.0.100",
                    "is_wired": True,
                },
            ],
            site="office",
        )
        fresh_db.insert_clients(
            ts,
            [
                {
                    "mac": "dd:00:00:00:00:01",
                    "hostname": "wh-scanner",
                    "ip": "10.0.1.100",
                    "is_wired": True,
                },
                {
                    "mac": "dd:00:00:00:00:02",
                    "hostname": "wh-tablet",
                    "ip": "10.0.1.101",
                    "is_wired": False,
                    "ssid": "WH-WiFi",
                },
            ],
            site="warehouse",
        )
        return TestClient(app)

    def test_sites_endpoint(self, multisite_client: TestClient):
        resp = multisite_client.get("/api/sites")
        data = resp.json()
        assert data["sites"] == ["office", "warehouse"]
        assert data["default"] == "office"

    def test_overview_isolates_sites(self, multisite_client: TestClient):
        resp_office = multisite_client.get("/api/overview?site=office")
        resp_wh = multisite_client.get("/api/overview?site=warehouse")
        office = resp_office.json()
        wh = resp_wh.json()

        assert office["wan"]["latency_ms"] == 10.0
        assert wh["wan"]["latency_ms"] == 30.0
        assert office["clients"]["total"] == 1
        assert wh["clients"]["total"] == 2

    def test_devices_isolates_sites(self, multisite_client: TestClient):
        resp = multisite_client.get("/api/devices?site=office")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Office-GW"

    def test_default_site_used_when_missing(self, multisite_client: TestClient):
        resp = multisite_client.get("/api/overview")
        data = resp.json()
        # Default is "office" (first in list)
        assert data["wan"]["latency_ms"] == 10.0

    def test_unknown_site_falls_back_to_default(self, multisite_client: TestClient):
        resp = multisite_client.get("/api/overview?site=bogus")
        data = resp.json()
        assert data["wan"]["latency_ms"] == 10.0


# ---------------------------------------------------------------------------
# Auth + data access integration
# ---------------------------------------------------------------------------


class TestAuthIntegration:
    """Verify auth middleware works end-to-end with data endpoints."""

    @pytest.fixture(autouse=True)
    def _enable_auth(self, monkeypatch):
        monkeypatch.setattr(config, "auth_username", "monitor")
        monkeypatch.setattr(config, "auth_password", "s3cret")

    def test_unauthenticated_returns_401_for_all_data_endpoints(
        self, integration_client: TestClient
    ):
        endpoints = [
            "/api/overview",
            "/api/clients",
            "/api/devices",
            "/api/wan/history",
            "/api/alarms",
            "/api/traffic/top-talkers",
            "/api/sites",
            "/api/export/clients",
            "/api/export/wan",
        ]
        for ep in endpoints:
            resp = integration_client.get(ep)
            assert resp.status_code == 401, f"{ep} should require auth"

    def test_health_always_accessible(self, integration_client: TestClient):
        resp = integration_client.get("/api/health")
        assert resp.status_code == 200

    def test_authenticated_can_access_all_endpoints(self, integration_client: TestClient):
        headers = _basic_auth("monitor", "s3cret")
        endpoints = ["/api/overview", "/api/clients", "/api/devices", "/api/sites"]
        for ep in endpoints:
            resp = integration_client.get(ep, headers=headers)
            assert resp.status_code == 200, f"{ep} should succeed with valid auth"

    def test_invalid_base64_returns_401(self, integration_client: TestClient):
        resp = integration_client.get(
            "/api/overview", headers={"Authorization": "Basic not-valid-b64!!!"}
        )
        assert resp.status_code == 401

    def test_malformed_auth_header_returns_401(self, integration_client: TestClient):
        resp = integration_client.get(
            "/api/overview", headers={"Authorization": "Bearer some-token"}
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Export pipeline integration
# ---------------------------------------------------------------------------


class TestExportIntegration:
    """Test the full export pipeline: seed data -> export JSON/CSV -> verify content."""

    def _seed_export_data(self, db: Database) -> None:
        now = time.time()
        for i in range(5):
            db.insert_wan(
                now - (i * 300),
                "ok",
                10.0 + i,
                "1.2.3.4",
                30.0,
                80.0,
            )
            db.insert_clients(
                now - (i * 300),
                [
                    {
                        "mac": f"aa:bb:cc:dd:ee:{i:02x}",
                        "hostname": f"host-{i}",
                        "ip": f"192.168.1.{100 + i}",
                        "is_wired": i % 2 == 0,
                    },
                ],
            )

    def test_export_clients_json_count(self, fresh_db: Database, integration_client: TestClient):
        self._seed_export_data(fresh_db)
        resp = integration_client.get("/api/export/clients?hours=1")
        data = resp.json()
        assert len(data) == 5

    def test_export_clients_csv_columns(self, fresh_db: Database, integration_client: TestClient):
        self._seed_export_data(fresh_db)
        resp = integration_client.get("/api/export/clients?format=csv&hours=1")
        assert resp.status_code == 200
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 5
        assert "mac" in rows[0]
        assert "hostname" in rows[0]
        assert "ip" in rows[0]

    def test_export_wan_json_count(self, fresh_db: Database, integration_client: TestClient):
        self._seed_export_data(fresh_db)
        resp = integration_client.get("/api/export/wan?hours=1")
        data = resp.json()
        assert len(data) == 5

    def test_export_wan_csv_has_latency(self, fresh_db: Database, integration_client: TestClient):
        self._seed_export_data(fresh_db)
        resp = integration_client.get("/api/export/wan?format=csv&hours=1")
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 5
        assert "latency_ms" in rows[0]

    def test_export_limit_param(self, fresh_db: Database, integration_client: TestClient):
        self._seed_export_data(fresh_db)
        resp = integration_client.get("/api/export/clients?hours=1&limit=2")
        data = resp.json()
        assert len(data) == 2

    def test_export_empty_db_csv(self, integration_client: TestClient):
        resp = integration_client.get("/api/export/wan?format=csv")
        assert resp.status_code == 200
        assert "no data" in resp.text

    def test_export_empty_db_json(self, integration_client: TestClient):
        resp = integration_client.get("/api/export/wan")
        data = resp.json()
        assert data == []


# ---------------------------------------------------------------------------
# Comparison endpoint integration
# ---------------------------------------------------------------------------


class TestComparisonIntegration:
    """Test historical comparison with data in both current and previous windows."""

    def test_latency_comparison_direction(
        self, fresh_db: Database, integration_client: TestClient
    ):
        now = time.time()
        # Current window: low latency
        for i in range(3):
            fresh_db.insert_wan(now - (i * 3600), "ok", 10.0, "1.2.3.4", 30.0, 80.0)
        # Previous window (168h ago): high latency
        for i in range(3):
            fresh_db.insert_wan(
                now - (168 * 3600) - (i * 3600), "ok", 50.0, "1.2.3.4", 30.0, 80.0
            )

        resp = integration_client.get("/api/compare?metric=latency&hours=24&offset_hours=168")
        data = resp.json()
        assert data["summary"]["direction"] == "better"
        assert data["summary"]["delta_pct"] < 0

    def test_client_count_comparison(self, fresh_db: Database, integration_client: TestClient):
        now = time.time()
        # Current: 3 clients
        fresh_db.insert_clients(
            now,
            [{"mac": f"aa:bb:cc:dd:ee:{i:02x}"} for i in range(3)],
        )
        # Previous: 1 client
        fresh_db.insert_clients(
            now - (168 * 3600),
            [{"mac": "aa:bb:cc:dd:ee:ff"}],
        )

        resp = integration_client.get("/api/compare?metric=client_count&hours=24&offset_hours=168")
        data = resp.json()
        assert data["summary"]["direction"] == "better"

    def test_comparison_no_previous_data(
        self, fresh_db: Database, integration_client: TestClient
    ):
        now = time.time()
        fresh_db.insert_wan(now, "ok", 15.0, "1.2.3.4", 30.0, 80.0)

        resp = integration_client.get("/api/compare?metric=latency&hours=24&offset_hours=168")
        data = resp.json()
        assert data["summary"]["previous_avg"] is None
        assert data["summary"]["delta_pct"] is None


# ---------------------------------------------------------------------------
# WebSocket integration
# ---------------------------------------------------------------------------


class TestWebSocketIntegration:
    """Test WebSocket connect/disconnect through the TestClient."""

    def test_ws_connect_without_auth(self, integration_client: TestClient, monkeypatch):
        monkeypatch.setattr(config, "auth_username", "")
        monkeypatch.setattr(config, "auth_password", "")
        # Need ws_manager on app.state
        from unifi_monitor.ws import ConnectionManager

        app.state.ws_manager = ConnectionManager()
        with integration_client.websocket_connect("/api/ws") as ws:
            # Connection accepted -- just close gracefully
            pass

    def test_ws_rejects_bad_token_when_auth_enabled(
        self, integration_client: TestClient, monkeypatch
    ):
        monkeypatch.setattr(config, "auth_username", "admin")
        monkeypatch.setattr(config, "auth_password", "secret")
        from unifi_monitor.ws import ConnectionManager

        app.state.ws_manager = ConnectionManager()
        with pytest.raises(Exception):
            with integration_client.websocket_connect("/api/ws?token=bad") as ws:
                ws.receive_text()


# ---------------------------------------------------------------------------
# DB cleanup integration
# ---------------------------------------------------------------------------


class TestCleanupIntegration:
    """Test that cleanup removes old data but preserves recent data, verified via API."""

    def test_cleanup_preserves_recent_data(
        self, fresh_db: Database, integration_client: TestClient
    ):
        now = time.time()
        # Recent data
        fresh_db.insert_wan(now, "ok", 15.0, "1.2.3.4", 30.0, 80.0)
        fresh_db.insert_devices(
            now, [{"mac": "aa:bb:cc:dd:ee:ff", "name": "GW", "state": 1}]
        )
        # Old data (30 days ago)
        old_ts = now - (30 * 24 * 3600)
        fresh_db.insert_wan(old_ts, "ok", 99.0, "5.6.7.8", 90.0, 90.0)
        fresh_db.insert_devices(
            old_ts, [{"mac": "11:22:33:44:55:66", "name": "OLD-GW", "state": 1}]
        )

        # Run cleanup with 7-day retention
        fresh_db.cleanup(retention_hours=168)

        # API should only return recent data
        resp = integration_client.get("/api/overview")
        data = resp.json()
        assert data["wan"]["latency_ms"] == 15.0
        assert data["devices"]["total"] == 1

        resp = integration_client.get("/api/devices")
        devices = resp.json()
        assert len(devices) == 1
        assert devices[0]["name"] == "GW"


# ---------------------------------------------------------------------------
# Error handling integration
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Test API behavior with edge cases and invalid inputs."""

    def test_query_validation_rejects_bad_params(self, integration_client: TestClient):
        # hours below minimum
        assert integration_client.get("/api/wan/history?hours=0").status_code == 422
        # limit below minimum
        assert integration_client.get("/api/clients?limit=0").status_code == 422
        # limit above maximum
        assert integration_client.get("/api/clients?limit=999").status_code == 422
        # invalid compare metric
        assert integration_client.get("/api/compare?metric=invalid").status_code == 422
        # missing required metric param
        assert integration_client.get("/api/compare").status_code == 422
        # invalid export format
        assert integration_client.get("/api/export/clients?format=xml").status_code == 422

    def test_empty_db_returns_safe_defaults(self, integration_client: TestClient):
        resp = integration_client.get("/api/overview")
        data = resp.json()
        assert data["wan"]["status"] == "no data"
        assert data["clients"]["total"] == 0
        assert data["devices"]["total"] == 0
        assert data["alarms"] == 0
        # WAN is None -> _compute_health deducts 40 ("WAN down")
        assert data["health_score"] == 60

    def test_empty_db_traffic_endpoints_return_empty(self, integration_client: TestClient):
        for ep in [
            "/api/traffic/top-talkers",
            "/api/traffic/top-destinations",
            "/api/traffic/top-ports",
            "/api/traffic/dns-queries",
            "/api/traffic/dns-top-clients",
            "/api/traffic/dns-top-servers",
        ]:
            resp = integration_client.get(ep)
            assert resp.status_code == 200
            assert resp.json() == [], f"{ep} should return empty list"

    def test_client_history_nonexistent_mac(self, integration_client: TestClient):
        resp = integration_client.get("/api/clients/ff:ff:ff:ff:ff:ff/history")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Health score integration with various network states
# ---------------------------------------------------------------------------


class TestHealthScoreIntegration:
    """Verify the weighted health score calculation through the API with various states."""

    def _setup_state(
        self,
        db: Database,
        wan_status: str = "ok",
        latency: float | None = 15.0,
        device_states: list[int] | None = None,
        n_alarms: int = 0,
    ) -> None:
        ts = time.time()
        db.insert_wan(ts, wan_status, latency, "1.2.3.4", 30.0, 80.0)
        if device_states is None:
            device_states = [1]
        db.insert_devices(
            ts,
            [
                {"mac": f"aa:bb:cc:dd:ee:{i:02x}", "name": f"dev-{i}", "state": s}
                for i, s in enumerate(device_states)
            ],
        )
        if n_alarms > 0:
            db.insert_alarms(
                ts,
                [
                    {"id": f"a{i}", "type": "EVT_TEST", "message": f"test {i}", "archived": False}
                    for i in range(n_alarms)
                ],
            )

    def test_perfect_health(self, fresh_db: Database, integration_client: TestClient):
        self._setup_state(fresh_db)
        resp = integration_client.get("/api/overview")
        assert resp.json()["health_score"] == 100

    def test_wan_down_drops_40(self, fresh_db: Database, integration_client: TestClient):
        self._setup_state(fresh_db, wan_status="down", latency=None)
        data = integration_client.get("/api/overview").json()
        assert data["health_score"] <= 60
        assert "WAN down" in data["health_factors"]

    def test_high_latency_penalty(self, fresh_db: Database, integration_client: TestClient):
        self._setup_state(fresh_db, latency=120.0)
        data = integration_client.get("/api/overview").json()
        assert data["health_score"] <= 90
        assert any("latency" in f.lower() for f in data["health_factors"])

    def test_device_offline_penalty(self, fresh_db: Database, integration_client: TestClient):
        self._setup_state(fresh_db, device_states=[1, 0])
        data = integration_client.get("/api/overview").json()
        assert data["health_score"] <= 85
        assert any("offline" in f for f in data["health_factors"])

    def test_multiple_alarms_penalty(self, fresh_db: Database, integration_client: TestClient):
        self._setup_state(fresh_db, n_alarms=4)
        data = integration_client.get("/api/overview").json()
        assert data["health_score"] <= 80
        assert any("alarm" in f for f in data["health_factors"])

    def test_combined_degradation(self, fresh_db: Database, integration_client: TestClient):
        self._setup_state(
            fresh_db, wan_status="down", latency=None, device_states=[1, 0, 0], n_alarms=3
        )
        data = integration_client.get("/api/overview").json()
        # WAN down (-40), 2 offline (-30), 3 alarms (-15) -> capped at 0
        assert data["health_score"] <= 15
