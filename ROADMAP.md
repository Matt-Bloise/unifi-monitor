# Roadmap

## v0.3.0
- [x] WebSocket live updates (replace polling)
- [x] Per-client detail view with signal/satisfaction charts
- [x] Configurable alert thresholds
- [x] Webhook notifications (Discord, Slack, ntfy, etc.)
- [x] User authentication (HTTP Basic Auth)
- [x] Data export (CSV/JSON)
- [x] Dark/light theme toggle

## v0.4.0 (Current)
- [x] DNS query logging (via NetFlow)
- [x] Multi-site support
- [x] Historical comparison (today vs last week)

## v0.5.0
- [ ] Grafana-compatible /metrics endpoint (Prometheus)
- [ ] Custom dashboard layouts
- [ ] Mobile-responsive PWA
- [ ] Anomaly detection (baseline learning + deviation alerts)

## Ideas
- InfluxDB/TimescaleDB backend option
- Plugin system for custom collectors
- Shared UniFi client library (with UnifiAgent)
- PersonalAI Discord bot integration (alert routing)
- SNMP polling as alternative to API
- Per-SSID / per-VLAN bandwidth breakdown
- Client roaming timeline visualization
- Firmware update tracking / changelog alerts
