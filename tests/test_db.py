# test_db.py -- Tests for SQLite database layer

import time
import tempfile
from pathlib import Path

from unifi_monitor.db import Database


class TestDatabase:
    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db = Database(self.tmp.name)

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
            {"mac": "aa:bb:cc:dd:ee:ff", "name": "Gateway", "model": "UCG-Max",
             "ip": "192.168.1.1", "state": 1, "cpu_pct": 30.0, "mem_pct": 80.0,
             "num_clients": 10, "satisfaction": 98, "tx_bytes_r": 1000.0, "rx_bytes_r": 2000.0},
        ]
        self.db.insert_devices(ts, devices)
        result = self.db.get_latest_devices()
        assert len(result) == 1
        assert result[0]["name"] == "Gateway"
        assert result[0]["mac"] == "aa:bb:cc:dd:ee:ff"

    def test_insert_and_get_clients(self):
        ts = time.time()
        clients = [
            {"mac": "11:22:33:44:55:66", "hostname": "laptop", "ip": "192.168.1.50",
             "is_wired": False, "ssid": "MyNetwork", "signal_dbm": -55,
             "satisfaction": 95, "channel": 36, "radio": "na",
             "tx_bytes": 1000000, "rx_bytes": 5000000, "tx_rate": 100.0, "rx_rate": 200.0},
        ]
        self.db.insert_clients(ts, clients)
        result = self.db.get_latest_clients()
        assert len(result) == 1
        assert result[0]["hostname"] == "laptop"
        assert result[0]["signal_dbm"] == -55

    def test_insert_netflow_and_top_talkers(self):
        ts = time.time()
        flows = [
            {"src_ip": "192.168.1.10", "dst_ip": "8.8.8.8",
             "src_port": 54321, "dst_port": 443, "protocol": 6,
             "bytes": 50000, "packets": 30},
            {"src_ip": "192.168.1.10", "dst_ip": "1.1.1.1",
             "src_port": 54322, "dst_port": 53, "protocol": 17,
             "bytes": 1000, "packets": 5},
            {"src_ip": "192.168.1.20", "dst_ip": "8.8.8.8",
             "src_port": 12345, "dst_port": 80, "protocol": 6,
             "bytes": 100000, "packets": 60},
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
            {"src_ip": "10.0.0.1", "dst_ip": "10.0.0.2",
             "src_port": 1, "dst_port": 443, "protocol": 6,
             "bytes": 5000, "packets": 10},
            {"src_ip": "10.0.0.1", "dst_ip": "10.0.0.3",
             "src_port": 2, "dst_port": 443, "protocol": 6,
             "bytes": 3000, "packets": 5},
            {"src_ip": "10.0.0.1", "dst_ip": "10.0.0.2",
             "src_port": 3, "dst_port": 80, "protocol": 6,
             "bytes": 1000, "packets": 2},
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
            {"src_ip": "10.0.0.1", "dst_ip": "10.0.0.2",
             "src_port": 1, "dst_port": 443, "protocol": 6,
             "bytes": 5000, "packets": 10},
        ]
        self.db.insert_netflow_batch(now, flows)
        result = self.db.get_bandwidth_timeseries(hours=1, bucket_minutes=5)
        assert len(result) >= 1
        assert result[0]["total_bytes"] == 5000
