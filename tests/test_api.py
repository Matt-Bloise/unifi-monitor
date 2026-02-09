# test_api.py -- Tests for REST API endpoints

from __future__ import annotations

import base64
import time

from fastapi.testclient import TestClient

from unifi_monitor.app import app
from unifi_monitor.config import config
from unifi_monitor.db import Database


class TestHealthEndpoint:
    def test_health_returns_ok(self, test_client: TestClient):
        resp = test_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "uptime_s" in data

    def test_health_includes_db_stats(self, test_client: TestClient):
        resp = test_client.get("/api/health")
        data = resp.json()
        assert "db_size_bytes" in data
        assert data["db_size_bytes"] > 0


class TestOverview:
    def test_overview_returns_data(self, test_client: TestClient):
        resp = test_client.get("/api/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "health_score" in data
        assert "health_factors" in data
        assert "wan" in data
        assert "clients" in data
        assert "devices" in data

    def test_overview_health_score_range(self, test_client: TestClient):
        resp = test_client.get("/api/overview")
        data = resp.json()
        assert 0 <= data["health_score"] <= 100

    def test_overview_with_empty_db(self, tmp_db: Database):
        app.state.db = tmp_db
        app.state.start_time = time.time()
        client = TestClient(app)
        resp = client.get("/api/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["wan"]["status"] == "no data"
        assert data["clients"]["total"] == 0


class TestClients:
    def test_clients_returns_paginated(self, test_client: TestClient):
        resp = test_client.get("/api/clients")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "data" in data
        assert data["total"] == 3

    def test_clients_pagination(self, test_client: TestClient):
        resp = test_client.get("/api/clients?offset=1&limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["offset"] == 1

    def test_clients_invalid_limit(self, test_client: TestClient):
        resp = test_client.get("/api/clients?limit=0")
        assert resp.status_code == 422

    def test_clients_invalid_limit_too_high(self, test_client: TestClient):
        resp = test_client.get("/api/clients?limit=9999")
        assert resp.status_code == 422

    def test_client_history(self, test_client: TestClient):
        resp = test_client.get("/api/clients/aa:11:22:33:44:55/history?hours=24")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1


class TestDevices:
    def test_devices_returns_list(self, test_client: TestClient):
        resp = test_client.get("/api/devices")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = [d["name"] for d in data]
        assert "Gateway" in names
        assert "AP" in names


class TestWANHistory:
    def test_wan_history(self, test_client: TestClient):
        resp = test_client.get("/api/wan/history?hours=24")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1

    def test_wan_history_invalid_hours(self, test_client: TestClient):
        resp = test_client.get("/api/wan/history?hours=-1")
        assert resp.status_code == 422

    def test_wan_history_hours_too_high(self, test_client: TestClient):
        resp = test_client.get("/api/wan/history?hours=99999")
        assert resp.status_code == 422


class TestTraffic:
    def test_top_talkers(self, test_client: TestClient):
        resp = test_client.get("/api/traffic/top-talkers?hours=1&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert "total_bytes_fmt" in data[0]

    def test_top_destinations(self, test_client: TestClient):
        resp = test_client.get("/api/traffic/top-destinations?hours=1&limit=10")
        assert resp.status_code == 200

    def test_top_ports(self, test_client: TestClient):
        resp = test_client.get("/api/traffic/top-ports?hours=1&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert "protocol_name" in data[0]

    def test_bandwidth_timeseries(self, test_client: TestClient):
        resp = test_client.get("/api/traffic/bandwidth?hours=1&bucket_minutes=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert "mbps" in data[0]


class TestAlarms:
    def test_alarms_returns_active(self, test_client: TestClient):
        resp = test_client.get("/api/alarms")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["type"] == "EVT_AP_Lost_Contact"


class TestHealthScoreCalculation:
    def test_healthy_network(self, test_client: TestClient):
        """All devices online, WAN ok, no alarms -> high score."""
        resp = test_client.get("/api/overview")
        data = resp.json()
        # Has 1 alarm so score won't be 100
        assert data["health_score"] >= 80

    def test_wan_down_score(self, tmp_db: Database):
        """WAN down should drop score by 40."""
        ts = time.time()
        tmp_db.insert_wan(ts, "down", None, None, 30.0, 80.0)
        tmp_db.insert_devices(
            ts,
            [
                {"mac": "aa:bb:cc:dd:ee:ff", "name": "GW", "state": 1},
            ],
        )
        app.state.db = tmp_db
        app.state.start_time = time.time()
        client = TestClient(app)
        resp = client.get("/api/overview")
        data = resp.json()
        assert data["health_score"] <= 60
        assert "WAN down" in data["health_factors"]

    def test_device_offline_score(self, tmp_db: Database):
        """Offline device should penalize score."""
        ts = time.time()
        tmp_db.insert_wan(ts, "ok", 10.0, "1.2.3.4", 30.0, 80.0)
        tmp_db.insert_devices(
            ts,
            [
                {"mac": "aa:bb:cc:dd:ee:ff", "name": "GW", "state": 1},
                {"mac": "11:22:33:44:55:66", "name": "AP", "state": 0},
            ],
        )
        app.state.db = tmp_db
        app.state.start_time = time.time()
        client = TestClient(app)
        resp = client.get("/api/overview")
        data = resp.json()
        assert data["health_score"] <= 85
        assert any("offline" in f for f in data["health_factors"])


class TestAuth:
    """HTTP Basic Auth middleware + WS token tests."""

    def _basic_header(self, user: str, password: str) -> dict:
        creds = base64.b64encode(f"{user}:{password}".encode()).decode()
        return {"Authorization": f"Basic {creds}"}

    def test_no_auth_configured_passes(self, test_client: TestClient, monkeypatch):
        monkeypatch.setattr(config, "auth_username", "")
        monkeypatch.setattr(config, "auth_password", "")
        resp = test_client.get("/api/overview")
        assert resp.status_code == 200

    def test_auth_configured_no_creds_returns_401(self, test_client: TestClient, monkeypatch):
        monkeypatch.setattr(config, "auth_username", "admin")
        monkeypatch.setattr(config, "auth_password", "secret")
        resp = test_client.get("/api/overview")
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers

    def test_auth_configured_valid_creds(self, test_client: TestClient, monkeypatch):
        monkeypatch.setattr(config, "auth_username", "admin")
        monkeypatch.setattr(config, "auth_password", "secret")
        resp = test_client.get("/api/overview", headers=self._basic_header("admin", "secret"))
        assert resp.status_code == 200

    def test_auth_configured_wrong_password(self, test_client: TestClient, monkeypatch):
        monkeypatch.setattr(config, "auth_username", "admin")
        monkeypatch.setattr(config, "auth_password", "secret")
        resp = test_client.get("/api/overview", headers=self._basic_header("admin", "wrong"))
        assert resp.status_code == 401

    def test_health_bypasses_auth(self, test_client: TestClient, monkeypatch):
        monkeypatch.setattr(config, "auth_username", "admin")
        monkeypatch.setattr(config, "auth_password", "secret")
        resp = test_client.get("/api/health")
        assert resp.status_code == 200

    def test_token_returns_hash_when_auth_enabled(self, test_client: TestClient, monkeypatch):
        monkeypatch.setattr(config, "auth_username", "admin")
        monkeypatch.setattr(config, "auth_password", "secret")
        resp = test_client.get("/api/auth/token", headers=self._basic_header("admin", "secret"))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["token"]) == 32

    def test_token_returns_empty_when_auth_disabled(self, test_client: TestClient, monkeypatch):
        monkeypatch.setattr(config, "auth_username", "")
        monkeypatch.setattr(config, "auth_password", "")
        resp = test_client.get("/api/auth/token")
        assert resp.status_code == 200
        assert resp.json()["token"] == ""

    def test_root_requires_auth(self, test_client: TestClient, monkeypatch):
        monkeypatch.setattr(config, "auth_username", "admin")
        monkeypatch.setattr(config, "auth_password", "secret")
        resp = test_client.get("/")
        assert resp.status_code == 401
