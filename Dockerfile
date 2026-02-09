FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e .

RUN mkdir -p data

ENV PYTHONUNBUFFERED=1

EXPOSE 8080
EXPOSE 2055/udp

ENTRYPOINT ["python", "-m", "unifi_monitor"]
