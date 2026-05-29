from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..services import queues
from ..templating import templates

router = APIRouter()


@router.get("/feed")
def feed(
    request: Request,
    queue: str = "must_read",
    category: str | None = None,
    source: str | None = None,
    min_score: float | None = None,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    active_queue = queue if queue in queues.QUEUES else "must_read"
    articles = queues.feed(
        db,
        settings,
        queue=active_queue,
        category=category,
        source=source,
        min_score=min_score,
    )

    return templates.TemplateResponse(
        request,
        "_card_list.html",
        {
            "request": request,
            "articles": articles,
            "settings": settings,
            "active_queue": active_queue,
        },
    )
