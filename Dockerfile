FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir --prefix=/install ".[netflow]"

FROM python:3.12-slim
LABEL org.opencontainers.image.source=https://github.com/Matt-Bloise/unifi-monitor
LABEL org.opencontainers.image.description="Real-time network monitoring dashboard for UniFi networks"
LABEL org.opencontainers.image.licenses=MIT
RUN groupadd -r monitor && useradd -r -g monitor monitor
WORKDIR /app
COPY --from=builder /install /usr/local
COPY src/ src/
RUN mkdir -p data && chown monitor:monitor data
USER monitor
ENV PYTHONUNBUFFERED=1
EXPOSE 8080 2055/udp
HEALTHCHECK --interval=30s --timeout=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/api/health')"
ENTRYPOINT ["python", "-m", "unifi_monitor"]
