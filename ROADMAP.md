# Roadmap

## v0.2.0 (Current)
- [x] WebSocket live updates (replace polling)
- [x] Per-client detail view with signal/satisfaction charts
- [x] Configurable alert thresholds
- [x] Webhook notifications (Discord, Slack, ntfy, etc.)
- [ ] DNS query logging (via NetFlow)

## v0.3.0
- [ ] Multi-site support
- [ ] User authentication (basic auth or API key)
- [ ] Data export (CSV/JSON)
- [ ] Grafana-compatible metrics endpoint (/metrics)
- [ ] Historical comparison (today vs last week)

## Ideas
- Prometheus exporter
- InfluxDB/TimescaleDB backend option
- Mobile-responsive PWA
- Plugin system for custom collectors
- Anomaly detection (baseline + deviation alerts)
