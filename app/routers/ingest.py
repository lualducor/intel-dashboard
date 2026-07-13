from __future__ import annotations

from fastapi import APIRouter
from starlette.responses import JSONResponse

from ..config import get_settings
from ..db import SessionLocal
from ..services import briefing as briefing_service
from ..services import horoscope as horoscope_service
from ..services import ingest as ingest_service

router = APIRouter(prefix="/ingest")


@router.post("/run")
async def run_ingest():
    result = await ingest_service.run_ingest()
    result["horoscope"] = await horoscope_service.refresh_horoscope()
    if not result.get("locked"):
        db = SessionLocal()
        try:
            generated = briefing_service.generate_briefing(db, get_settings())
            result["briefing_id"] = generated.id
        finally:
            db.close()
    return JSONResponse(result)


@router.post("/run/{slug}")
async def run_ingest_source(slug: str):
    result = await ingest_service.run_ingest(slug=slug, force=True)
    return JSONResponse(result)


@router.post("/test/{slug}")
async def test_source(slug: str):
    result = await ingest_service.test_source(slug)
    return JSONResponse(result)
