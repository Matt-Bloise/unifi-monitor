# db.py -- SQLite storage for time-series metrics
# WAL mode for concurrent reads from web API while poller writes.
# Retention policy enforced by periodic cleanup.

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)

DB_PATH = Path(os.getenv("DB_PATH", "data/monitor.db"))

_VALID_TABLES = frozenset({"wan_metrics", "devices", "clients", "netflow", "alarms"})


def _dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


class Database:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DB_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._last_write_ts: float = 0.0
        self._init_schema()

    @property
    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(str(self.path), check_same_thread=False)
            conn.row_factory = _dict_factory
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return self._local.conn

    def _init_schema(self) -> None:
        conn = self._conn
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS wan_metrics (
                ts REAL NOT NULL,
                status TEXT,
                latency_ms REAL,
                download_bps REAL,
                upload_bps REAL,
                wan_ip TEXT,
                cpu_pct REAL,
                mem_pct REAL
            );
            CREATE INDEX IF NOT EXISTS idx_wan_ts ON wan_metrics(ts);

            CREATE TABLE IF NOT EXISTS devices (
                ts REAL NOT NULL,
                mac TEXT NOT NULL,
                name TEXT,
                model TEXT,
                ip TEXT,
                state INTEGER,
                cpu_pct REAL,
                mem_pct REAL,
                num_clients INTEGER,
                satisfaction INTEGER,
                tx_bytes_r REAL,
                rx_bytes_r REAL
            );
            CREATE INDEX IF NOT EXISTS idx_dev_ts ON devices(ts);
            CREATE INDEX IF NOT EXISTS idx_dev_mac_ts ON devices(mac, ts);

            CREATE TABLE IF NOT EXISTS clients (
                ts REAL NOT NULL,
                mac TEXT NOT NULL,
                hostname TEXT,
                ip TEXT,
                is_wired INTEGER,
                ssid TEXT,
                signal_dbm INTEGER,
                satisfaction INTEGER,
                channel INTEGER,
                radio TEXT,
                tx_bytes REAL,
                rx_bytes REAL,
                tx_rate REAL,
                rx_rate REAL
            );
            CREATE INDEX IF NOT EXISTS idx_cli_ts ON clients(ts);
            CREATE INDEX IF NOT EXISTS idx_cli_mac_ts ON clients(mac, ts);

            CREATE TABLE IF NOT EXISTS netflow (
                ts REAL NOT NULL,
                src_ip TEXT,
                dst_ip TEXT,
                src_port INTEGER,
                dst_port INTEGER,
                protocol INTEGER,
                bytes INTEGER,
                packets INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_nf_ts ON netflow(ts);

            CREATE TABLE IF NOT EXISTS alarms (
                ts REAL NOT NULL,
                alarm_id TEXT,
                type TEXT,
                message TEXT,
                device_name TEXT,
                archived INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_alarm_ts ON alarms(ts);
        """)
        conn.commit()

    # -- Write methods --

    def insert_wan(
        self,
        ts: float,
        status: str,
        latency_ms: float | None,
        wan_ip: str | None,
        cpu_pct: float | None,
        mem_pct: float | None,
        download_bps: float | None = None,
        upload_bps: float | None = None,
    ) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO wan_metrics VALUES (?,?,?,?,?,?,?,?)",
                (ts, status, latency_ms, download_bps, upload_bps, wan_ip, cpu_pct, mem_pct),
            )
        self._last_write_ts = ts

    def insert_devices(self, ts: float, devices: list[dict]) -> None:
        rows = [
            (
                ts,
                d["mac"],
                d.get("name"),
                d.get("model"),
                d.get("ip"),
                d.get("state"),
                d.get("cpu_pct"),
                d.get("mem_pct"),
                d.get("num_clients"),
                d.get("satisfaction"),
                d.get("tx_bytes_r"),
                d.get("rx_bytes_r"),
            )
            for d in devices
        ]
        with self._conn:
            self._conn.executemany("INSERT INTO devices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        self._last_write_ts = ts

    def insert_clients(self, ts: float, clients: list[dict]) -> None:
        rows = [
            (
                ts,
                c["mac"],
                c.get("hostname"),
                c.get("ip"),
                int(c.get("is_wired", False)),
                c.get("ssid"),
                c.get("signal_dbm"),
                c.get("satisfaction"),
                c.get("channel"),
                c.get("radio"),
                c.get("tx_bytes"),
                c.get("rx_bytes"),
                c.get("tx_rate"),
                c.get("rx_rate"),
            )
            for c in clients
        ]
        with self._conn:
            self._conn.executemany("INSERT INTO clients VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        self._last_write_ts = ts

    def insert_netflow_batch(self, ts: float, flows: list[dict]) -> None:
        rows = [
            (
                ts,
                f["src_ip"],
                f["dst_ip"],
                f["src_port"],
                f["dst_port"],
                f["protocol"],
                f["bytes"],
                f["packets"],
            )
            for f in flows
        ]
        with self._conn:
            self._conn.executemany("INSERT INTO netflow VALUES (?,?,?,?,?,?,?,?)", rows)
        self._last_write_ts = ts

    def insert_alarms(self, ts: float, alarms: list[dict]) -> None:
        rows = [
            (
                ts,
                a.get("id"),
                a.get("type"),
                a.get("message"),
                a.get("device_name"),
                int(a.get("archived", False)),
            )
            for a in alarms
        ]
        with self._conn:
            self._conn.executemany("INSERT INTO alarms VALUES (?,?,?,?,?,?)", rows)
        self._last_write_ts = ts

    # -- Read methods --

    def get_wan_history(self, hours: float = 24) -> list[dict]:
        cutoff = time.time() - (hours * 3600)
        return self._conn.execute(
            "SELECT * FROM wan_metrics WHERE ts > ? ORDER BY ts", (cutoff,)
        ).fetchall()

    def get_latest_wan(self) -> dict | None:
        row = self._conn.execute("SELECT * FROM wan_metrics ORDER BY ts DESC LIMIT 1").fetchone()
        return row

    def get_latest_devices(self) -> list[dict]:
        latest_ts = self._conn.execute("SELECT MAX(ts) as ts FROM devices").fetchone()
        if not latest_ts or not latest_ts["ts"]:
            return []
        return self._conn.execute(
            "SELECT * FROM devices WHERE ts = ?", (latest_ts["ts"],)
        ).fetchall()

    def get_latest_clients(self) -> list[dict]:
        latest_ts = self._conn.execute("SELECT MAX(ts) as ts FROM clients").fetchone()
        if not latest_ts or not latest_ts["ts"]:
            return []
        return self._conn.execute(
            "SELECT * FROM clients WHERE ts = ?", (latest_ts["ts"],)
        ).fetchall()

    def get_client_history(self, mac: str, hours: float = 24) -> list[dict]:
        cutoff = time.time() - (hours * 3600)
        return self._conn.execute(
            "SELECT * FROM clients WHERE mac = ? AND ts > ? ORDER BY ts",
            (mac, cutoff),
        ).fetchall()

    def get_top_talkers(self, hours: float = 1, limit: int = 20) -> list[dict]:
        cutoff = time.time() - (hours * 3600)
        return self._conn.execute(
            """SELECT src_ip, SUM(bytes) as total_bytes, SUM(packets) as total_packets,
                      COUNT(*) as flow_count
               FROM netflow WHERE ts > ?
               GROUP BY src_ip ORDER BY total_bytes DESC LIMIT ?""",
            (cutoff, limit),
        ).fetchall()

    def get_top_destinations(self, hours: float = 1, limit: int = 20) -> list[dict]:
        cutoff = time.time() - (hours * 3600)
        return self._conn.execute(
            """SELECT dst_ip, SUM(bytes) as total_bytes, SUM(packets) as total_packets,
                      COUNT(*) as flow_count
               FROM netflow WHERE ts > ?
               GROUP BY dst_ip ORDER BY total_bytes DESC LIMIT ?""",
            (cutoff, limit),
        ).fetchall()

    def get_top_ports(self, hours: float = 1, limit: int = 20) -> list[dict]:
        cutoff = time.time() - (hours * 3600)
        return self._conn.execute(
            """SELECT dst_port, protocol, SUM(bytes) as total_bytes, COUNT(*) as flow_count
               FROM netflow WHERE ts > ?
               GROUP BY dst_port, protocol ORDER BY total_bytes DESC LIMIT ?""",
            (cutoff, limit),
        ).fetchall()

    def get_dns_queries(self, hours: float = 1, limit: int = 100) -> list[dict]:
        cutoff = time.time() - (hours * 3600)
        return self._conn.execute(
            """SELECT src_ip, dst_ip, SUM(bytes) as total_bytes, SUM(packets) as total_packets,
                      COUNT(*) as query_count
               FROM netflow WHERE ts > ? AND dst_port IN (53, 853) AND protocol IN (6, 17)
               GROUP BY src_ip, dst_ip ORDER BY query_count DESC LIMIT ?""",
            (cutoff, limit),
        ).fetchall()

    def get_dns_top_clients(self, hours: float = 1, limit: int = 20) -> list[dict]:
        cutoff = time.time() - (hours * 3600)
        return self._conn.execute(
            """SELECT src_ip, SUM(bytes) as total_bytes, SUM(packets) as total_packets,
                      COUNT(*) as query_count
               FROM netflow WHERE ts > ? AND dst_port IN (53, 853) AND protocol IN (6, 17)
               GROUP BY src_ip ORDER BY query_count DESC LIMIT ?""",
            (cutoff, limit),
        ).fetchall()

    def get_dns_top_servers(self, hours: float = 1, limit: int = 20) -> list[dict]:
        cutoff = time.time() - (hours * 3600)
        return self._conn.execute(
            """SELECT dst_ip, SUM(bytes) as total_bytes, SUM(packets) as total_packets,
                      COUNT(*) as query_count
               FROM netflow WHERE ts > ? AND dst_port IN (53, 853) AND protocol IN (6, 17)
               GROUP BY dst_ip ORDER BY query_count DESC LIMIT ?""",
            (cutoff, limit),
        ).fetchall()

    def get_bandwidth_timeseries(self, hours: float = 24, bucket_minutes: int = 5) -> list[dict]:
        cutoff = time.time() - (hours * 3600)
        bucket_secs = bucket_minutes * 60
        return self._conn.execute(
            "SELECT CAST(ts / ? AS INTEGER) * ? as bucket,"
            "       SUM(bytes) as total_bytes, SUM(packets) as total_packets"
            " FROM netflow WHERE ts > ?"
            " GROUP BY bucket ORDER BY bucket",
            (bucket_secs, bucket_secs, cutoff),
        ).fetchall()

    def get_active_alarms(self) -> list[dict]:
        latest_ts = self._conn.execute("SELECT MAX(ts) as ts FROM alarms").fetchone()
        if not latest_ts or not latest_ts["ts"]:
            return []
        return self._conn.execute(
            "SELECT * FROM alarms WHERE ts = ? AND archived = 0", (latest_ts["ts"],)
        ).fetchall()

    def get_clients_export(self, hours: float = 24, limit: int = 10000) -> list[dict]:
        cutoff = time.time() - (hours * 3600)
        return self._conn.execute(
            "SELECT * FROM clients WHERE ts > ? ORDER BY ts DESC LIMIT ?",
            (cutoff, limit),
        ).fetchall()

    def get_wan_export(self, hours: float = 24, limit: int = 10000) -> list[dict]:
        cutoff = time.time() - (hours * 3600)
        return self._conn.execute(
            "SELECT * FROM wan_metrics WHERE ts > ? ORDER BY ts DESC LIMIT ?",
            (cutoff, limit),
        ).fetchall()

    def get_db_stats(self) -> dict:
        """Return row counts per table, DB file size, and last write timestamp."""
        stats: dict = {"last_write_ts": self._last_write_ts}
        for table in _VALID_TABLES:
            row = self._conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
            stats[f"{table}_rows"] = row["cnt"] if row else 0
        try:
            stats["db_size_bytes"] = self.path.stat().st_size
        except OSError:
            stats["db_size_bytes"] = 0
        return stats

    # -- Maintenance --

    def cleanup(self, retention_hours: int = 168) -> None:
        cutoff = time.time() - (retention_hours * 3600)
        for table in _VALID_TABLES:
            self._conn.execute(f"DELETE FROM {table} WHERE ts < ?", (cutoff,))
        self._conn.commit()
        self._conn.execute("PRAGMA optimize")
        log.info("DB cleanup: removed data older than %dh", retention_hours)
