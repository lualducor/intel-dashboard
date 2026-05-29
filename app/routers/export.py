from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.responses import Response

from ..db import get_db
from ..services import exporter

router = APIRouter()

MEDIA = {"md": "text/markdown", "csv": "text/csv", "json": "application/json"}


@router.get("/export.{fmt}")
def export(
    fmt: str,
    status: str | None = None,
    for_content: bool = False,
    db: Session = Depends(get_db),
):
    if fmt not in MEDIA:
        raise HTTPException(404, "unsupported format")
    body = exporter.export_as(
        db,
        fmt,
        status_in=([status] if status else None),
        for_content=for_content,
    )
    return Response(content=body, media_type=MEDIA[fmt])
