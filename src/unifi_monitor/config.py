# config.py -- All configuration from environment variables
# No config files to manage. docker-compose.yml sets env vars.

import os


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
