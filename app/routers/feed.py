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
    page: int = 1,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    active_queue = queue if queue in queues.QUEUES else "must_read"
    current_page = max(1, page)
    page_size = max(1, min(settings.feed_page_size, 200))
    result = queues.feed(
        db,
        settings,
        queue=active_queue,
        category=category,
        source=source,
        min_score=min_score,
        limit=page_size + 1,
        offset=(current_page - 1) * page_size,
    )
    articles = result[:page_size]

    return templates.TemplateResponse(
        request,
        "_card_page.html" if current_page > 1 else "_card_list.html",
        {
            "request": request,
            "articles": articles,
            "settings": settings,
            "active_queue": active_queue,
            "page": current_page,
            "page_size": page_size,
            "has_more": len(result) > page_size,
            "category": category,
            "source": source,
            "min_score": min_score,
        },
    )
