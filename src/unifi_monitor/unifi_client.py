# unifi_client.py -- UniFi OS API client
# Thin requests.Session wrapper with CSRF handling and session reuse.
# Works with any UniFi OS gateway (UCG-Max, UDM, UDR, UDM-SE, etc.).

from __future__ import annotations

import logging

import requests
import urllib3

log = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15  # seconds


class UnifiAuthError(Exception):
    """Authentication failed."""


class UnifiAPIError(Exception):
    """Non-OK response from UniFi API."""


class UnifiClient:
    def __init__(
        self, host: str, username: str, password: str, site: str = "default", port: int = 443
    ) -> None:
        self.base_url = f"https://{host}:{port}" if port != 443 else f"https://{host}"
        self.username = username
        self.password = password
        self.site = site
        self.session = requests.Session()
        self.session.verify = False
        # Suppress SSL warnings only for this session's urllib3 pool
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self._csrf_token: str | None = None
        self._authenticated = False

    def login(self) -> None:
        resp = self.session.post(
            f"{self.base_url}/api/auth/login",
            json={"username": self.username, "password": self.password},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            self._authenticated = False
            raise UnifiAuthError(f"Login failed: {resp.status_code}")
        self._update_csrf(resp)
        if not self._csrf_token:
            raise UnifiAuthError("Login succeeded but no CSRF token in response")
        self._authenticated = True

    def ensure_auth(self) -> None:
        if not self._authenticated:
            self.login()

    def close(self) -> None:
        """Close the underlying requests session."""
        self.session.close()
        self._authenticated = False

    def _update_csrf(self, resp: requests.Response) -> None:
        token = resp.headers.get("X-Updated-CSRF-Token") or resp.headers.get("X-CSRF-Token")
        if token:
            self._csrf_token = token

    def _csrf_headers(self) -> dict[str, str]:
        return {"X-CSRF-Token": self._csrf_token} if self._csrf_token else {}

    def _request(
        self, method: str, path: str, json_body: dict | None = None, retry_auth: bool = True
    ) -> dict:
        resp = self.session.request(
            method,
            f"{self.base_url}{path}",
            json=json_body,
            headers=self._csrf_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        self._update_csrf(resp)

        if resp.status_code == 401 and retry_auth:
            self._authenticated = False
            self.login()
            return self._request(method, path, json_body=json_body, retry_auth=False)

        if resp.status_code not in (200, 201):
            raise UnifiAPIError(f"{method} {path} -> {resp.status_code}: {resp.text[:300]}")

        return resp.json()

    def _get(self, path: str) -> dict:
        return self._request("GET", path)

    def _extract(self, envelope: dict) -> list[dict]:
        meta = envelope.get("meta", {})
        if meta.get("rc") != "ok":
            raise UnifiAPIError(f"API error: {meta.get('msg', 'unknown')}")
        return envelope.get("data", [])

    def _site(self, suffix: str) -> str:
        return f"/proxy/network/api/s/{self.site}/{suffix}"

    # -- Read endpoints --

    def get_health(self) -> list[dict]:
        return self._extract(self._get(self._site("stat/health")))

    def get_devices(self) -> list[dict]:
        return self._extract(self._get(self._site("stat/device")))

    def get_clients(self) -> list[dict]:
        return self._extract(self._get(self._site("stat/sta")))

    def get_alarms(self) -> list[dict]:
        return self._extract(self._get(self._site("stat/alarm")))

    def get_events(self, limit: int = 50) -> list[dict]:
        return self._extract(self._get(self._site(f"stat/event?_limit={limit}")))

    def get_dpi(self) -> list[dict]:
        return self._extract(self._get(self._site("stat/sitedpi")))
