# app.py -- FastAPI application with background tasks
# Single process: web server + UniFi poller + NetFlow listener + DB cleanup.
# Entry point: `python -m unifi_monitor` or `unifi-monitor` CLI.

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import config
from .db import Database
from .poller import Poller
from .api import routes

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background tasks on startup, clean up on shutdown."""
    db = Database()
    routes.db = db

    # Start UniFi API poller
    poller = Poller(db)
    poller_task = asyncio.create_task(poller.run())

    # Start NetFlow collector
    nf_transport = None
    if config.netflow_enabled:
        from .netflow.collector import start_collector
        try:
            nf_transport = await start_collector(db, config.netflow_host, config.netflow_port)
        except Exception as e:
            log.warning("NetFlow collector failed to start: %s", e)

    # Periodic DB cleanup
    async def cleanup_loop():
        while True:
            await asyncio.sleep(3600)  # Every hour
            try:
                db.cleanup(config.retention_hours)
            except Exception as e:
                log.warning("DB cleanup error: %s", e)

    cleanup_task = asyncio.create_task(cleanup_loop())

    log.info("UniFi Monitor started -- dashboard at http://%s:%d", config.web_host, config.web_port)
    yield

    # Shutdown
    poller.stop()
    poller_task.cancel()
    cleanup_task.cancel()
    if nf_transport:
        nf_transport.close()
    log.info("UniFi Monitor stopped")


app = FastAPI(title="UniFi Monitor", version="0.1.0", lifespan=lifespan)
app.include_router(routes.router)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    uvicorn.run(
        "unifi_monitor.app:app",
        host=config.web_host,
        port=config.web_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
