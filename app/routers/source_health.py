from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Source, SourceFetchLog
from ..services.source_health import derive_status
from ..templating import templates

router = APIRouter()


@router.get("/sources/health")
def health(request: Request, db: Session = Depends(get_db)):
    sources = db.scalars(select(Source)).all()
    rows = []
    for source in sources:
        log = db.scalars(
            select(SourceFetchLog)
            .where(
                SourceFetchLog.source_id == source.id,
                SourceFetchLog.ok.is_(False),
            )
            .order_by(SourceFetchLog.started_at.desc(), SourceFetchLog.id.desc())
            .limit(1)
        ).first()
        rows.append(
            {
                "source": source,
                "status": derive_status(source),
                "last_error_message": log.error if log and log.error else "",
            }
        )

    return templates.TemplateResponse(request, "source_health.html", {"rows": rows})
