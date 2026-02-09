# test_db.py -- Tests for SQLite database layer

from __future__ import annotations

import time
from pathlib import Path

from unifi_monitor.db import Database


class TestDatabase:
    def setup_method(self, method):
        import tempfile

        self._tmpdir = tempfile.mkdtemp()
        self.db = Database(Path(self._tmpdir) / "test.db")

    def test_insert_and_get_wan(self):
        ts = time.time()
        self.db.insert_wan(ts, "ok", 15.5, "1.2.3.4", 30.0, 80.0)
        latest = self.db.get_latest_wan()
        assert latest is not None
        assert latest["status"] == "ok"
        assert latest["latency_ms"] == 15.5
        assert latest["wan_ip"] == "1.2.3.4"

    def test_insert_and_get_devices(self):
        ts = time.time()
        devices = [
            {
                "mac": "aa:bb:cc:dd:ee:ff",
                "name": "Gateway",
                "model": "UCG-Max",
                "ip": "192.168.1.1",
                "state": 1,
                "cpu_pct": 30.0,
                "mem_pct": 80.0,
                "num_clients": 10,
                "satisfaction": 98,
                "tx_bytes_r": 1000.0,
                "rx_bytes_r": 2000.0,
            },
        ]
        self.db.insert_devices(ts, devices)
        result = self.db.get_latest_devices()
        assert len(result) == 1
        assert result[0]["name"] == "Gateway"
        assert result[0]["mac"] == "aa:bb:cc:dd:ee:ff"

    def test_insert_and_get_clients(self):
        ts = time.time()
        clients = [
            {
                "mac": "11:22:33:44:55:66",
                "hostname": "laptop",
                "ip": "192.168.1.50",
                "is_wired": False,
                "ssid": "MyNetwork",
                "signal_dbm": -55,
                "satisfaction": 95,
                "channel": 36,
                "radio": "na",
                "tx_bytes": 1000000,
                "rx_bytes": 5000000,
                "tx_rate": 100.0,
                "rx_rate": 200.0,
            },
        ]
        self.db.insert_clients(ts, clients)
        result = self.db.get_latest_clients()
        assert len(result) == 1
        assert result[0]["hostname"] == "laptop"
        assert result[0]["signal_dbm"] == -55

    def test_insert_netflow_and_top_talkers(self):
        ts = time.time()
        flows = [
            {
                "src_ip": "192.168.1.10",
                "dst_ip": "8.8.8.8",
                "src_port": 54321,
                "dst_port": 443,
                "protocol": 6,
                "bytes": 50000,
                "packets": 30,
            },
            {
                "src_ip": "192.168.1.10",
                "dst_ip": "1.1.1.1",
                "src_port": 54322,
                "dst_port": 53,
                "protocol": 17,
                "bytes": 1000,
                "packets": 5,
            },
            {
                "src_ip": "192.168.1.20",
                "dst_ip": "8.8.8.8",
                "src_port": 12345,
                "dst_port": 80,
                "protocol": 6,
                "bytes": 100000,
                "packets": 60,
            },
        ]
        self.db.insert_netflow_batch(ts, flows)

        talkers = self.db.get_top_talkers(hours=1, limit=10)
        assert len(talkers) == 2
        # 192.168.1.20 has more bytes
        assert talkers[0]["src_ip"] == "192.168.1.20"
        assert talkers[0]["total_bytes"] == 100000

    def test_top_ports(self):
        ts = time.time()
        flows = [
            {
                "src_ip": "10.0.0.1",
                "dst_ip": "10.0.0.2",
                "src_port": 1,
                "dst_port": 443,
                "protocol": 6,
                "bytes": 5000,
                "packets": 10,
            },
            {
                "src_ip": "10.0.0.1",
                "dst_ip": "10.0.0.3",
                "src_port": 2,
                "dst_port": 443,
                "protocol": 6,
                "bytes": 3000,
                "packets": 5,
            },
            {
                "src_ip": "10.0.0.1",
                "dst_ip": "10.0.0.2",
                "src_port": 3,
                "dst_port": 80,
                "protocol": 6,
                "bytes": 1000,
                "packets": 2,
            },
        ]
        self.db.insert_netflow_batch(ts, flows)
        ports = self.db.get_top_ports(hours=1, limit=10)
        assert len(ports) == 2
        assert ports[0]["dst_port"] == 443
        assert ports[0]["total_bytes"] == 8000

    def test_wan_history(self):
        now = time.time()
        self.db.insert_wan(now - 3600, "ok", 10.0, "1.2.3.4", 25.0, 75.0)
        self.db.insert_wan(now - 1800, "ok", 15.0, "1.2.3.4", 28.0, 78.0)
        self.db.insert_wan(now, "ok", 12.0, "1.2.3.4", 30.0, 80.0)

        history = self.db.get_wan_history(hours=2)
        assert len(history) == 3

    def test_cleanup_removes_old_data(self):
        old_ts = time.time() - 999999
        self.db.insert_wan(old_ts, "ok", 10.0, "1.2.3.4", 25.0, 75.0)
        self.db.cleanup(retention_hours=1)
        assert self.db.get_latest_wan() is None

    def test_bandwidth_timeseries(self):
        now = time.time()
        flows = [
            {
                "src_ip": "10.0.0.1",
                "dst_ip": "10.0.0.2",
                "src_port": 1,
                "dst_port": 443,
                "protocol": 6,
                "bytes": 5000,
                "packets": 10,
            },
        ]
        self.db.insert_netflow_batch(now, flows)
        result = self.db.get_bandwidth_timeseries(hours=1, bucket_minutes=5)
        assert len(result) >= 1
        assert result[0]["total_bytes"] == 5000

    def test_get_db_stats(self):
        ts = time.time()
        self.db.insert_wan(ts, "ok", 10.0, "1.2.3.4", 30.0, 80.0)
        self.db.insert_devices(
            ts,
            [
                {"mac": "aa:bb:cc:dd:ee:ff", "name": "GW", "state": 1},
            ],
        )
        stats = self.db.get_db_stats()
        assert stats["wan_metrics_rows"] == 1
        assert stats["devices_rows"] == 1
        assert stats["db_size_bytes"] > 0
        assert stats["last_write_ts"] == ts

    def test_cleanup_with_valid_tables(self):
        """Verify cleanup only touches known tables."""
        ts = time.time()
        self.db.insert_wan(ts, "ok", 10.0, "1.2.3.4", 30.0, 80.0)
        self.db.insert_devices(ts, [{"mac": "aa:bb:cc:dd:ee:ff"}])
        self.db.insert_clients(ts, [{"mac": "11:22:33:44:55:66"}])
        flows = [
            {
                "src_ip": "10.0.0.1",
                "dst_ip": "10.0.0.2",
                "src_port": 1,
                "dst_port": 443,
                "protocol": 6,
                "bytes": 100,
                "packets": 1,
            }
        ]
        self.db.insert_netflow_batch(ts, flows)
        self.db.insert_alarms(ts, [{"id": "a1", "type": "test"}])

        # All data present
        stats = self.db.get_db_stats()
        assert stats["wan_metrics_rows"] == 1
        assert stats["netflow_rows"] == 1

        # Cleanup should not error
        self.db.cleanup(retention_hours=99999)
        # Data still present (not old enough)
        stats = self.db.get_db_stats()
        assert stats["wan_metrics_rows"] == 1

    def test_client_history(self):
        now = time.time()
        self.db.insert_clients(
            now - 1800,
            [
                {
                    "mac": "aa:bb:cc:dd:ee:ff",
                    "hostname": "test",
                    "ip": "192.168.1.10",
                    "is_wired": False,
                    "ssid": "Net",
                    "signal_dbm": -60,
                    "satisfaction": 90,
                    "channel": 36,
                    "radio": "na",
                    "tx_bytes": 100,
                    "rx_bytes": 200,
                    "tx_rate": 10.0,
                    "rx_rate": 20.0,
                },
            ],
        )
        self.db.insert_clients(
            now,
            [
                {
                    "mac": "aa:bb:cc:dd:ee:ff",
                    "hostname": "test",
                    "ip": "192.168.1.10",
                    "is_wired": False,
                    "ssid": "Net",
                    "signal_dbm": -55,
                    "satisfaction": 95,
                    "channel": 36,
                    "radio": "na",
                    "tx_bytes": 200,
                    "rx_bytes": 400,
                    "tx_rate": 15.0,
                    "rx_rate": 25.0,
                },
            ],
        )
        history = self.db.get_client_history("aa:bb:cc:dd:ee:ff", hours=1)
        assert len(history) == 2


class TestDns:
    def setup_method(self, method):
        import tempfile

        self._tmpdir = tempfile.mkdtemp()
        self.db = Database(Path(self._tmpdir) / "test.db")

    def _insert_dns_flows(self):
        ts = time.time()
        flows = [
            {
                "src_ip": "192.168.1.50",
                "dst_ip": "1.1.1.1",
                "src_port": 54322,
                "dst_port": 53,
                "protocol": 17,
                "bytes": 1000,
                "packets": 5,
            },
            {
                "src_ip": "192.168.1.50",
                "dst_ip": "8.8.8.8",
                "src_port": 54323,
                "dst_port": 53,
                "protocol": 17,
                "bytes": 2000,
                "packets": 10,
            },
            {
                "src_ip": "192.168.1.10",
                "dst_ip": "1.1.1.1",
                "src_port": 54324,
                "dst_port": 853,
                "protocol": 6,
                "bytes": 500,
                "packets": 3,
            },
            {
                "src_ip": "192.168.1.10",
                "dst_ip": "8.8.8.8",
                "src_port": 54325,
                "dst_port": 443,
                "protocol": 6,
                "bytes": 50000,
                "packets": 30,
            },
        ]
        self.db.insert_netflow_batch(ts, flows)
        return ts

    def test_dns_queries(self):
        self._insert_dns_flows()
        rows = self.db.get_dns_queries(hours=1, limit=100)
        # 3 DNS flows -> 3 unique src_ip/dst_ip pairs
        assert len(rows) == 3
        # Top by query_count -- all have count 1, so order by count desc
        assert all(r["query_count"] >= 1 for r in rows)

    def test_dns_top_clients(self):
        self._insert_dns_flows()
        rows = self.db.get_dns_top_clients(hours=1, limit=20)
        assert len(rows) == 2
        # 192.168.1.50 has 2 DNS flows, 192.168.1.10 has 1
        assert rows[0]["src_ip"] == "192.168.1.50"
        assert rows[0]["query_count"] == 2

    def test_dns_top_servers(self):
        self._insert_dns_flows()
        rows = self.db.get_dns_top_servers(hours=1, limit=20)
        assert len(rows) == 2
        # 1.1.1.1 has 2 DNS flows, 8.8.8.8 has 1
        assert rows[0]["dst_ip"] == "1.1.1.1"
        assert rows[0]["query_count"] == 2

    def test_dns_empty_db(self):
        assert self.db.get_dns_queries() == []
        assert self.db.get_dns_top_clients() == []
        assert self.db.get_dns_top_servers() == []


class TestMultiSite:
    def setup_method(self, method):
        import tempfile

        self._tmpdir = tempfile.mkdtemp()
        self.db = Database(Path(self._tmpdir) / "test.db")

    def test_site_column_exists(self):
        cols = [
            r["name"] for r in self.db._conn.execute("PRAGMA table_info(wan_metrics)").fetchall()
        ]
        assert "site" in cols

    def test_insert_and_query_by_site(self):
        ts = time.time()
        self.db.insert_wan(ts, "ok", 10.0, "1.2.3.4", 30.0, 80.0, site="siteA")
        self.db.insert_wan(ts, "ok", 20.0, "5.6.7.8", 40.0, 90.0, site="siteB")
        a = self.db.get_latest_wan(site="siteA")
        b = self.db.get_latest_wan(site="siteB")
        assert a["latency_ms"] == 10.0
        assert b["latency_ms"] == 20.0

    def test_default_site(self):
        ts = time.time()
        self.db.insert_wan(ts, "ok", 15.0, "1.2.3.4", 30.0, 80.0)
        wan = self.db.get_latest_wan()
        assert wan is not None
        assert wan["site"] == "default"

    def test_latest_devices_filters_by_site(self):
        ts = time.time()
        self.db.insert_devices(ts, [{"mac": "aa:bb:cc:dd:ee:ff", "name": "GW"}], site="siteA")
        self.db.insert_devices(ts, [{"mac": "11:22:33:44:55:66", "name": "AP"}], site="siteB")
        a = self.db.get_latest_devices(site="siteA")
        b = self.db.get_latest_devices(site="siteB")
        assert len(a) == 1
        assert a[0]["name"] == "GW"
        assert len(b) == 1
        assert b[0]["name"] == "AP"

    def test_cleanup_all_sites(self):
        old_ts = time.time() - 999999
        self.db.insert_wan(old_ts, "ok", 10.0, "1.2.3.4", 30.0, 80.0, site="siteA")
        self.db.insert_wan(old_ts, "ok", 20.0, "5.6.7.8", 40.0, 90.0, site="siteB")
        self.db.cleanup(retention_hours=1)
        assert self.db.get_latest_wan(site="siteA") is None
        assert self.db.get_latest_wan(site="siteB") is None


class TestComparison:
    def setup_method(self, method):
        import tempfile

        self._tmpdir = tempfile.mkdtemp()
        self.db = Database(Path(self._tmpdir) / "test.db")

    def test_latency_with_both_windows(self):
        now = time.time()
        # Current window: last 24h
        for i in range(3):
            self.db.insert_wan(now - (i * 3600), "ok", 15.0 + i, "1.2.3.4", 30.0, 80.0)
        # Previous window: 168h ago (last week)
        for i in range(3):
            self.db.insert_wan(
                now - (168 * 3600) - (i * 3600), "ok", 25.0 + i, "1.2.3.4", 30.0, 80.0
            )
        result = self.db.get_comparison("latency", hours=24, offset_hours=168)
        assert "current" in result
        assert "previous" in result
        assert "summary" in result
        s = result["summary"]
        assert s["current_avg"] is not None
        assert s["previous_avg"] is not None
        # Current avg ~16, previous avg ~26 -> lower is better -> "better"
        assert s["direction"] == "better"
        assert s["delta_pct"] is not None
        assert s["delta_pct"] < 0  # decrease = negative delta

    def test_bandwidth_comparison(self):
        now = time.time()
        flows = [
            {
                "src_ip": "10.0.0.1",
                "dst_ip": "10.0.0.2",
                "src_port": 1,
                "dst_port": 443,
                "protocol": 6,
                "bytes": 5000,
                "packets": 10,
            },
        ]
        self.db.insert_netflow_batch(now, flows)
        self.db.insert_netflow_batch(now - (168 * 3600), flows)
        result = self.db.get_comparison("bandwidth", hours=24, offset_hours=168)
        assert len(result["current"]) >= 1
        assert len(result["previous"]) >= 1

    def test_client_count_comparison(self):
        now = time.time()
        clients = [{"mac": "aa:bb:cc:dd:ee:ff", "hostname": "test"}]
        self.db.insert_clients(now, clients)
        self.db.insert_clients(now - (168 * 3600), clients)
        result = self.db.get_comparison("client_count", hours=24, offset_hours=168)
        assert len(result["current"]) >= 1

    def test_unknown_metric(self):
        result = self.db.get_comparison("bogus")
        assert "error" in result

    def test_no_previous_data(self):
        now = time.time()
        self.db.insert_wan(now, "ok", 15.0, "1.2.3.4", 30.0, 80.0)
        result = self.db.get_comparison("latency", hours=24, offset_hours=168)
        s = result["summary"]
        # No previous data -> delta is None
        assert s["current_avg"] is not None
        assert s["previous_avg"] is None
        assert s["delta_pct"] is None


class TestEmptyDefaults:
    """Extracted from TestDatabase for clarity."""

    def setup_method(self, method):
        import tempfile

        self._tmpdir = tempfile.mkdtemp()
        self.db = Database(Path(self._tmpdir) / "test.db")

    def test_empty_db_returns_sensible_defaults(self):
        assert self.db.get_latest_wan() is None
        assert self.db.get_latest_devices() == []
        assert self.db.get_latest_clients() == []
        assert self.db.get_active_alarms() == []
        assert self.db.get_top_talkers() == []
        assert self.db.get_wan_history() == []
