# conftest.py -- Shared test fixtures

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from unifi_monitor.db import Database


@pytest.fixture
def tmp_db(tmp_path: Path) -> Database:
    """Fresh empty database in a temp directory."""
    return Database(tmp_path / "test.db")


@pytest.fixture
def populated_db(tmp_db: Database) -> Database:
    """Database pre-loaded with sample data."""
    ts = time.time()

    # WAN metrics
    tmp_db.insert_wan(ts, "ok", 15.5, "1.2.3.4", 30.0, 80.0, 500000.0, 100000.0)

    # Devices
    tmp_db.insert_devices(
        ts,
        [
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
            {
                "mac": "11:22:33:44:55:66",
                "name": "AP",
                "model": "U7-Pro",
                "ip": "192.168.1.2",
                "state": 1,
                "cpu_pct": 5.0,
                "mem_pct": 40.0,
                "num_clients": 8,
                "satisfaction": 95,
                "tx_bytes_r": 500.0,
                "rx_bytes_r": 800.0,
            },
        ],
    )

    # Clients
    tmp_db.insert_clients(
        ts,
        [
            {
                "mac": "aa:11:22:33:44:55",
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
            {
                "mac": "bb:11:22:33:44:55",
                "hostname": "phone",
                "ip": "192.168.1.51",
                "is_wired": False,
                "ssid": "MyNetwork",
                "signal_dbm": -70,
                "satisfaction": 80,
                "channel": 6,
                "radio": "ng",
                "tx_bytes": 500000,
                "rx_bytes": 2000000,
                "tx_rate": 50.0,
                "rx_rate": 80.0,
            },
            {
                "mac": "cc:11:22:33:44:55",
                "hostname": "desktop",
                "ip": "192.168.1.10",
                "is_wired": True,
                "ssid": None,
                "signal_dbm": None,
                "satisfaction": 100,
                "channel": None,
                "radio": None,
                "tx_bytes": 10000000,
                "rx_bytes": 50000000,
                "tx_rate": None,
                "rx_rate": None,
            },
        ],
    )

    # NetFlow
    tmp_db.insert_netflow_batch(
        ts,
        [
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
                "src_ip": "192.168.1.50",
                "dst_ip": "1.1.1.1",
                "src_port": 54322,
                "dst_port": 53,
                "protocol": 17,
                "bytes": 1000,
                "packets": 5,
            },
        ],
    )

    # Alarms
    tmp_db.insert_alarms(
        ts,
        [
            {
                "id": "alarm1",
                "type": "EVT_AP_Lost_Contact",
                "message": "AP lost",
                "device_name": "AP",
                "archived": False,
            },
        ],
    )

    return tmp_db


@pytest.fixture
def test_client(populated_db: Database) -> TestClient:
    """FastAPI TestClient with DB dependency override."""
    from unifi_monitor.app import app

    app.state.db = populated_db
    app.state.start_time = time.time()
    return TestClient(app)
