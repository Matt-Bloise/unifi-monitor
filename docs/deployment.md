# Deployment

## Docker Compose (recommended)

```bash
git clone https://github.com/Matt-Bloise/unifi-monitor.git
cd unifi-monitor
cp .env.example .env
# Edit .env with your gateway credentials
docker compose up -d
```

### docker-compose.yml

```yaml
services:
  monitor:
    build: .
    ports:
      - "${WEB_PORT:-8080}:8080"
      - "${NETFLOW_PORT:-2055}:2055/udp"
    volumes:
      - monitor-data:/app/data
    env_file:
      - .env
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 256M
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  monitor-data:
```

Key points:

- **Port 8080**: Web dashboard and REST API
- **Port 2055/udp**: NetFlow/IPFIX collector
- **Volume `monitor-data`**: Persists SQLite database across container restarts
- **256M memory limit**: Sufficient for single-network monitoring
- **Log rotation**: 3 files at 10MB each

### Dockerfile

Multi-stage build based on `python:3.12-slim`:

1. **Builder stage**: Installs Python dependencies (including optional `netflow`)
2. **Runtime stage**: Copies installed packages, runs as non-root `monitor` user
3. **Healthcheck**: Queries `/api/health` every 30 seconds

### Rebuild

After code changes:

```bash
docker compose up -d --build
```

### View logs

```bash
docker compose logs -f monitor
```

## Local Development

```bash
pip install -e ".[dev,netflow]"
cp .env.example .env
# Edit .env
python -m unifi_monitor
```

The dashboard is available at `http://localhost:8080`.

## Systemd

For running directly on a Linux host:

```ini
[Unit]
Description=UniFi Monitor
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 -m unifi_monitor
WorkingDirectory=/home/user/unifi-monitor
EnvironmentFile=/home/user/unifi-monitor/.env
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now unifi-monitor
```

## Reverse Proxy

### Nginx

```nginx
server {
    listen 443 ssl;
    server_name monitor.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

The `Upgrade` and `Connection` headers are required for WebSocket proxying.

### Caddy

```
monitor.example.com {
    reverse_proxy localhost:8080
}
```

Caddy handles WebSocket upgrades automatically.

## Security

- Set `AUTH_USERNAME` and `AUTH_PASSWORD` to enable HTTP Basic Auth
- Without auth, bind to `localhost` or place behind a reverse proxy
- `/api/health` bypasses auth for Docker healthchecks
- WebSocket uses a separate hour-based token from `GET /api/auth/token`
- The Docker container runs as a non-root user (`monitor`)

## Healthcheck

The built-in healthcheck queries `GET /api/health`:

```bash
curl -s http://localhost:8080/api/health
# {"status":"ok","uptime_s":3600.5,"last_write_ts":1234567890.123,"db_size_bytes":2310144}
```

Docker reports container health based on this endpoint (30s interval, 5s timeout).
