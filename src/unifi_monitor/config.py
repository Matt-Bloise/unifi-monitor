# config.py -- All configuration from environment variables
# Loads .env file if present, then reads os.environ.
# Docker sets env vars directly; local dev uses .env file.

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

log = logging.getLogger(__name__)

# Walk up from config.py to find .env (supports both src layout and installed)
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")
# Also try cwd (Docker WORKDIR or wherever the user runs from)
load_dotenv(override=False)


def _safe_int(
    name: str, default: int, min_val: int | None = None, max_val: int | None = None
) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        val = int(raw)
    except (ValueError, TypeError):
        log.warning("Invalid integer for %s=%r, using default %d", name, raw, default)
        return default
    if min_val is not None and val < min_val:
        log.warning("%s=%d below minimum %d, using %d", name, val, min_val, min_val)
        return min_val
    if max_val is not None and val > max_val:
        log.warning("%s=%d above maximum %d, using %d", name, val, max_val, max_val)
        return max_val
    return val


class Config:
    # UniFi gateway
    unifi_host: str = os.getenv("UNIFI_HOST", "192.168.1.1")
    unifi_username: str = os.getenv("UNIFI_USERNAME", "admin")
    unifi_password: str = os.getenv("UNIFI_PASSWORD", "")
    unifi_site: str = os.getenv("UNIFI_SITE", "default")
    unifi_port: int = _safe_int("UNIFI_PORT", 443, min_val=1, max_val=65535)

    # Web server
    web_host: str = os.getenv("WEB_HOST", "0.0.0.0")
    web_port: int = _safe_int("WEB_PORT", 8080, min_val=1, max_val=65535)

    # NetFlow/IPFIX
    netflow_enabled: bool = os.getenv("NETFLOW_ENABLED", "true").lower() == "true"
    netflow_host: str = os.getenv("NETFLOW_HOST", "0.0.0.0")
    netflow_port: int = _safe_int("NETFLOW_PORT", 2055, min_val=1, max_val=65535)

    # Polling
    poll_interval: int = _safe_int("POLL_INTERVAL", 30, min_val=5)

    # Data retention
    retention_hours: int = _safe_int("RETENTION_HOURS", 168, min_val=1)

    # Alerts
    alert_webhook_url: str = os.getenv("ALERT_WEBHOOK_URL", "")
    alert_cooldown: int = _safe_int("ALERT_COOLDOWN", 300, min_val=30)


config = Config()
