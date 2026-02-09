# config.py -- All configuration from environment variables
# Loads .env file if present, then reads os.environ.
# Docker sets env vars directly; local dev uses .env file.

import os
from pathlib import Path

from dotenv import load_dotenv

# Walk up from config.py to find .env (supports both src layout and installed)
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")
# Also try cwd (Docker WORKDIR or wherever the user runs from)
load_dotenv(override=False)


class Config:
    # UniFi gateway
    unifi_host: str = os.getenv("UNIFI_HOST", "192.168.1.1")
    unifi_username: str = os.getenv("UNIFI_USERNAME", "admin")
    unifi_password: str = os.getenv("UNIFI_PASSWORD", "")
    unifi_site: str = os.getenv("UNIFI_SITE", "default")
    unifi_port: int = int(os.getenv("UNIFI_PORT", "443"))

    # Web server
    web_host: str = os.getenv("WEB_HOST", "0.0.0.0")
    web_port: int = int(os.getenv("WEB_PORT", "8080"))

    # NetFlow/IPFIX
    netflow_enabled: bool = os.getenv("NETFLOW_ENABLED", "true").lower() == "true"
    netflow_host: str = os.getenv("NETFLOW_HOST", "0.0.0.0")
    netflow_port: int = int(os.getenv("NETFLOW_PORT", "2055"))

    # Polling
    poll_interval: int = int(os.getenv("POLL_INTERVAL", "30"))

    # Data retention
    retention_hours: int = int(os.getenv("RETENTION_HOURS", "168"))  # 7 days


config = Config()
