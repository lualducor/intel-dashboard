import logging
import sys
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routers import (
    actions,
    briefing,
    clip,
    content,
    dashboard,
    export,
    feed,
    horoscope,
    ingest,
    notes,
    saved,
    score_debug,
    search,
    source_health,
    sources_admin,
)
from .templating import templates  # noqa: F401  (registers the to_bogota_local filter)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.ensure_directories()

    root_logger = logging.getLogger()
    if not root_logger.handlers:
        root_logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler = RotatingFileHandler(
            str(settings.log_path), maxBytes=5 * 1024 * 1024, backupCount=3
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

        logging.info("INTEL starting")

    yield


app = FastAPI(title="INTEL", lifespan=lifespan)

app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).parent / "static")),
    name="static",
)

app.include_router(dashboard.router)
app.include_router(ingest.router)
app.include_router(horoscope.router)
app.include_router(feed.router)
app.include_router(content.router)
app.include_router(saved.router)
app.include_router(search.router)
app.include_router(briefing.router)
app.include_router(clip.router)
app.include_router(source_health.router)
app.include_router(sources_admin.router)
app.include_router(export.router)
app.include_router(score_debug.router)
app.include_router(notes.router)
app.include_router(actions.router)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
