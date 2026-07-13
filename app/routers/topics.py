from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Article, Source
from ..templating import templates

router = APIRouter()
TOPICS = {"colombia": "Colombia / Bogotá", "crypto": "Crypto"}


@router.get("/topics/{topic}")
def topic_page(
    topic: str,
    request: Request,
    page: int = 1,
    days: int = 30,
    source: str | None = None,
    db: Session = Depends(get_db),
):
    if topic not in TOPICS:
        raise HTTPException(404, "unknown topic")
    current_page = max(1, page)
    safe_days = max(1, min(days, 3650))
    page_size = max(1, min(get_settings().feed_page_size, 200))
    cutoff = datetime.now(timezone.utc) - timedelta(days=safe_days)
    conditions = [
        Article.topic == topic,
        Article.status.not_in(["archived", "ignored"]),
        or_(Article.published_at.is_(None), Article.published_at >= cutoff),
    ]
    if source:
        conditions.append(Article.source.has(slug=source))

    total = db.scalar(select(func.count()).select_from(Article).where(*conditions)) or 0
    articles = list(
        db.scalars(
            select(Article)
            .where(*conditions)
            .order_by(
                Article.published_at.desc(),
                Article.final_score.desc(),
                Article.id.desc(),
            )
            .offset((current_page - 1) * page_size)
            .limit(page_size)
        )
    )
    sources = list(
        db.scalars(select(Source).where(Source.topic == topic).order_by(Source.name))
    )
    return templates.TemplateResponse(
        request,
        "topic.html",
        {
            "topic": topic,
            "topic_title": TOPICS[topic],
            "articles": articles,
            "sources": sources,
            "selected_source": source,
            "days": safe_days,
            "page": current_page,
            "total": total,
            "has_more": current_page * page_size < total,
            "settings": get_settings(),
        },
    )
