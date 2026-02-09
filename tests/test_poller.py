# test_poller.py -- Tests for UniFi API data parsing

from __future__ import annotations

from unifi_monitor.poller import (
    _parse_alarm,
    _parse_client,
    _parse_device,
    _parse_wan,
    _safe_float,
    _safe_int,
)


class TestSafeConversions:
    def test_safe_int_none(self):
        assert _safe_int(None) is None

    def test_safe_int_valid(self):
        assert _safe_int("42") == 42
        assert _safe_int(42) == 42

    def test_safe_int_invalid(self):
        assert _safe_int("abc") is None
        assert _safe_int([]) is None

    def test_safe_float_none(self):
        assert _safe_float(None) is None

    def test_safe_float_valid(self):
        assert _safe_float("3.14") == 3.14
        assert _safe_float(3.14) == 3.14

    def test_safe_float_invalid(self):
        assert _safe_float("abc") is None
        assert _safe_float({}) is None


class TestParseWan:
    def test_extracts_wan_subsystem(self):
        health = [
            {"subsystem": "wlan", "status": "ok"},
            {
                "subsystem": "wan",
                "status": "ok",
                "wan_ip": "1.2.3.4",
                "latency": "15.5",
                "gw_system-stats": {"cpu": "30", "mem": "80"},
            },
            {"subsystem": "lan", "status": "ok"},
        ]
        wan = _parse_wan(health)
        assert wan is not None
        assert wan["status"] == "ok"
        assert wan["wan_ip"] == "1.2.3.4"
        assert wan["latency_ms"] == 15.5
        assert wan["cpu_pct"] == 30.0
        assert wan["mem_pct"] == 80.0

    def test_no_wan_subsystem(self):
        health = [{"subsystem": "wlan", "status": "ok"}]
        assert _parse_wan(health) is None

    def test_empty_health(self):
        assert _parse_wan([]) is None

    def test_fallback_wan_ip(self):
        health = [
            {"subsystem": "wan", "status": "ok", "gw_wan_ip": "5.6.7.8", "gw_system-stats": {}}
        ]
        wan = _parse_wan(health)
        assert wan["wan_ip"] == "5.6.7.8"


class TestParseDevice:
    def test_normal_device(self):
        raw = {
            "mac": "aa:bb:cc:dd:ee:ff",
            "name": "Gateway",
            "model": "UCG-Max",
            "ip": "192.168.1.1",
            "state": 1,
            "num_sta": 10,
            "system-stats": {"cpu": "30", "mem": "80"},
        }
        d = _parse_device(raw)
        assert d is not None
        assert d["mac"] == "aa:bb:cc:dd:ee:ff"
        assert d["name"] == "Gateway"
        assert d["cpu_pct"] == 30.0

    def test_missing_mac_returns_none(self):
        raw = {"name": "NoMAC", "model": "Something"}
        assert _parse_device(raw) is None

    def test_boolean_model_fallback(self):
        raw = {"mac": "aa:bb:cc:dd:ee:ff", "model": True, "model_long_name": "Real Name"}
        d = _parse_device(raw)
        assert d["model"] == "Real Name"

    def test_missing_fields_defaults(self):
        raw = {"mac": "aa:bb:cc:dd:ee:ff"}
        d = _parse_device(raw)
        assert d["state"] == 0
        assert d["cpu_pct"] is None
        assert d["num_clients"] == 0


class TestParseClient:
    def test_wireless_client(self):
        raw = {
            "mac": "11:22:33:44:55:66",
            "hostname": "laptop",
            "ip": "192.168.1.50",
            "is_wired": False,
            "essid": "MyNet",
            "signal": -55,
            "satisfaction": 95,
            "channel": 36,
            "radio": "na",
            "tx_bytes": 1000,
            "rx_bytes": 2000,
        }
        c = _parse_client(raw)
        assert c is not None
        assert c["mac"] == "11:22:33:44:55:66"
        assert c["ssid"] == "MyNet"
        assert c["signal_dbm"] == -55
        assert c["is_wired"] is False

    def test_wired_client(self):
        raw = {
            "mac": "aa:bb:cc:dd:ee:ff",
            "hostname": "desktop",
            "ip": "192.168.1.10",
            "is_wired": True,
        }
        c = _parse_client(raw)
        assert c["is_wired"] is True
        assert c["ssid"] is None

    def test_missing_mac_returns_none(self):
        raw = {"hostname": "NoMAC"}
        assert _parse_client(raw) is None

    def test_hostname_fallback_chain(self):
        raw = {"mac": "aa:bb:cc:dd:ee:ff", "name": "DevName"}
        c = _parse_client(raw)
        assert c["hostname"] == "DevName"


class TestParseAlarm:
    def test_normal_alarm(self):
        raw = {
            "_id": "abc123",
            "type": "EVT_AP_Lost_Contact",
            "msg": "AP lost contact",
            "device_name": "AP",
        }
        a = _parse_alarm(raw)
        assert a["id"] == "abc123"
        assert a["type"] == "EVT_AP_Lost_Contact"
        assert a["message"] == "AP lost contact"

    def test_alarm_key_fallback(self):
        raw = {"_id": "x", "key": "EVT_Something", "message": "Something"}
        a = _parse_alarm(raw)
        assert a["type"] == "EVT_Something"
        assert a["message"] == "Something"

    def test_alarm_archived(self):
        raw = {"_id": "x", "archived": True}
        a = _parse_alarm(raw)
        assert a["archived"] is True
