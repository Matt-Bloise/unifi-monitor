# unifi_client.py -- UniFi OS API client
# Thin requests.Session wrapper with CSRF handling and session reuse.
# Works with any UniFi OS gateway (UCG-Max, UDM, UDR, UDM-SE, etc.).

import logging

import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

log = logging.getLogger(__name__)


class UnifiAuthError(Exception):
    """Authentication failed."""


class UnifiAPIError(Exception):
    """Non-OK response from UniFi API."""


class UnifiClient:
    def __init__(self, host: str, username: str, password: str,
                 site: str = "default", port: int = 443):
        self.base_url = f"https://{host}:{port}" if port != 443 else f"https://{host}"
        self.username = username
        self.password = password
        self.site = site
        self.session = requests.Session()
        self.session.verify = False
        self._csrf_token = None
        self._authenticated = False

    def login(self):
        resp = self.session.post(
            f"{self.base_url}/api/auth/login",
            json={"username": self.username, "password": self.password},
        )
        if resp.status_code != 200:
            self._authenticated = False
            raise UnifiAuthError(f"Login failed: {resp.status_code}")
        self._update_csrf(resp)
        self._authenticated = True

    def ensure_auth(self):
        if not self._authenticated:
            self.login()

    def _update_csrf(self, resp):
        token = resp.headers.get("X-Updated-CSRF-Token") or resp.headers.get("X-CSRF-Token")
        if token:
            self._csrf_token = token

    def _csrf_headers(self):
        return {"X-CSRF-Token": self._csrf_token} if self._csrf_token else {}

    def _request(self, method, path, json_body=None, retry_auth=True):
        resp = self.session.request(
            method,
            f"{self.base_url}{path}",
            json=json_body,
            headers=self._csrf_headers(),
        )
        self._update_csrf(resp)

        if resp.status_code == 401 and retry_auth:
            self._authenticated = False
            self.login()
            return self._request(method, path, json_body=json_body, retry_auth=False)

        if resp.status_code not in (200, 201):
            raise UnifiAPIError(f"{method} {path} -> {resp.status_code}: {resp.text[:300]}")

        return resp.json()

    def _get(self, path):
        return self._request("GET", path)

    def _extract(self, envelope):
        meta = envelope.get("meta", {})
        if meta.get("rc") != "ok":
            raise UnifiAPIError(f"API error: {meta.get('msg', 'unknown')}")
        return envelope.get("data", [])

    def _site(self, suffix):
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
