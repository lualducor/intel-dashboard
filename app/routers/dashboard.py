from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..services import briefing
from ..services import queues
from ..templating import templates

router = APIRouter()


@router.get("/")
def index(
    request: Request,
    queue: str = "must_read",
    db: Session = Depends(get_db),
):
    settings = get_settings()
    active_queue = queue if queue in queues.QUEUES else "must_read"
    counts = queues.queue_counts(db, settings)
    articles = queues.feed(db, settings, queue=active_queue)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "settings": settings,
            "active_queue": active_queue,
            "counts": counts,
            "articles": articles,
            "colombia": queues.side_panel_colombia(db),
            "horoscope": queues.horoscope_today(db),
            "briefing": briefing.get_latest_briefing(db),
        },
    )
