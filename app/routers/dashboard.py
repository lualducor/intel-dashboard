from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Source, SourceFetchLog
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
    return _dashboard_response(request, queue, db, tech_only=False)


@router.get("/tech")
def tech(
    request: Request,
    queue: str = "must_read",
    db: Session = Depends(get_db),
):
    return _dashboard_response(request, queue, db, tech_only=True)


def _dashboard_response(
    request: Request,
    queue: str,
    db: Session,
    *,
    tech_only: bool,
):
    settings = get_settings()
    active_queue = queue if queue in queues.QUEUES else "must_read"
    source_slugs = queues.TECH_HARDWARE_SOURCE_SLUGS if tech_only else None
    counts = queues.queue_counts(db, settings, source_slugs=source_slugs)
    page_size = max(1, min(settings.feed_page_size, 200))
    page = queues.feed(
        db,
        settings,
        queue=active_queue,
        source_slugs=source_slugs,
        limit=page_size + 1,
    )
    articles = page[:page_size]
    source_conditions = [Source.active.is_(True)]
    if source_slugs is not None:
        source_conditions.append(Source.slug.in_(source_slugs))
    last_refresh = select(func.max(SourceFetchLog.finished_at))
    if source_slugs is not None:
        last_refresh = last_refresh.join(Source).where(Source.slug.in_(source_slugs))
    source_stats = {
        "active": db.scalar(
            select(func.count()).select_from(Source).where(*source_conditions)
        )
        or 0,
        "failing": db.scalar(
            select(func.count())
            .select_from(Source)
            .where(*source_conditions, Source.consecutive_failures > 0)
        )
        or 0,
        "last_refresh": db.scalar(last_refresh),
    }
    latest_briefing = None if tech_only else briefing.get_latest_briefing(db)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "settings": settings,
            "active_queue": active_queue,
            "counts": counts,
            "articles": articles,
            "page": 1,
            "page_size": page_size,
            "has_more": len(page) > page_size,
            "colombia": [] if tech_only else queues.side_panel_colombia(db),
            "crypto": [] if tech_only else queues.side_panel_crypto(db),
            "horoscope": None if tech_only else queues.horoscope_today(db),
            "briefing": latest_briefing,
            "briefing_groups": briefing.article_groups(db, latest_briefing),
            "source_stats": source_stats,
            "tech_only": tech_only,
            "feed_view": "tech" if tech_only else None,
        },
    )
