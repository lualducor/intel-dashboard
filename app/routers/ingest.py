from __future__ import annotations

from fastapi import APIRouter
from starlette.responses import JSONResponse

from ..services import ingest as ingest_service

router = APIRouter(prefix="/ingest")


@router.post("/run")
async def run_ingest():
    result = await ingest_service.run_ingest()
    return JSONResponse(result)


@router.post("/run/{slug}")
async def run_ingest_source(slug: str):
    result = await ingest_service.run_ingest(slug=slug, force=True)
    return JSONResponse(result)


@router.post("/test/{slug}")
async def test_source(slug: str):
    result = await ingest_service.test_source(slug)
    return JSONResponse(result)
