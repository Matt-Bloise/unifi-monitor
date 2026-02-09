# test_export.py -- Tests for data export endpoints

from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient

from unifi_monitor.db import Database


class TestExportClients:
    def test_json_returns_list(self, test_client: TestClient):
        resp = test_client.get("/api/export/clients")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3  # populated_db has 3 clients

    def test_csv_returns_csv(self, test_client: TestClient):
        resp = test_client.get("/api/export/clients?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]
        assert "Content-Disposition" in resp.headers
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) == 3
        assert "mac" in rows[0]

    def test_default_format_is_json(self, test_client: TestClient):
        resp = test_client.get("/api/export/clients")
        assert resp.headers["content-type"].startswith("application/json")

    def test_invalid_format_returns_422(self, test_client: TestClient):
        resp = test_client.get("/api/export/clients?format=xml")
        assert resp.status_code == 422

    def test_limit_param(self, test_client: TestClient):
        resp = test_client.get("/api/export/clients?limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1


class TestExportWan:
    def test_json_returns_list(self, test_client: TestClient):
        resp = test_client.get("/api/export/wan")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_csv_has_latency_column(self, test_client: TestClient):
        resp = test_client.get("/api/export/wan?format=csv")
        assert resp.status_code == 200
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)
        assert len(rows) >= 1
        assert "latency_ms" in rows[0]

    def test_empty_db_returns_no_data(self, tmp_db: Database):
        import time

        from unifi_monitor.app import app

        app.state.db = tmp_db
        app.state.start_time = time.time()
        app.state.sites = ["default"]
        client = TestClient(app)
        resp = client.get("/api/export/wan?format=csv")
        assert resp.status_code == 200
        assert "no data" in resp.text
