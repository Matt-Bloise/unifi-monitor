# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.0] - 2026-02-09

### Added
- WebSocket live updates -- dashboard receives instant updates when poller completes
- Connection status badge (Live / Polling / Disconnected) with auto-reconnect
- Per-client detail view -- click any client row for 24h signal/satisfaction charts
- Configurable alert engine with webhook notifications (Discord, Slack, ntfy)
- Default alert rules: WAN down, health < 50, device offline, latency > 100ms
- Per-rule cooldown to prevent notification spam
- REST polling fallback when WebSocket is unavailable
- Tab visibility awareness for WebSocket connections

### Changed
- Dashboard updates via WebSocket instead of 15s REST polling (REST kept as fallback)
- httpx added as core dependency (used by alert webhook delivery)
- pytest-asyncio added as dev dependency (WebSocket/alert async tests)

## [0.1.0] - 2026-02-08

### Added
- Initial release
- FastAPI REST API with 11 endpoints
- UniFi API poller with per-endpoint error isolation
- SQLite storage with WAL mode and retention cleanup
- NetFlow/IPFIX collector (UDP 2055) with v5/v9/v10 parser
- Dashboard with Chart.js: health score, WAN latency, bandwidth, client table
- Client sorting, signal strength color coding, device status cards
- Stale data detection with yellow/red banners
- Auto-pause polling when browser tab is hidden
- Docker healthcheck endpoint (`/api/health`)
- Weighted health score: WAN (40%), devices (30%), alarms (30%)
- Session reuse to prevent UniFi 429 rate limiting
- Multi-stage Docker build with non-root user
- CI: ruff lint + format check + pytest

[0.2.0]: https://github.com/Matt-Bloise/unifi-monitor/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Matt-Bloise/unifi-monitor/releases/tag/v0.1.0
