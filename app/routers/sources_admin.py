from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Source
from ..templating import templates

router = APIRouter()


@router.get("/sources")
def sources_page(request: Request, db: Session = Depends(get_db)):
    srcs = db.scalars(select(Source).order_by(Source.topic, Source.name)).all()
    return templates.TemplateResponse(request, "sources.html", {"sources": srcs})


@router.post("/sources/{slug}/toggle")
def toggle(slug: str, request: Request, db: Session = Depends(get_db)):
    source = db.scalar(select(Source).where(Source.slug == slug))
    if source is None:
        raise HTTPException(404, "source not found")
    source.active = not source.active
    db.commit()
    db.refresh(source)
    return templates.TemplateResponse(request, "_source_row.html", {"source": source})


@router.post("/sources/{slug}/edit")
def edit(
    slug: str,
    request: Request,
    trust_score: float = Form(...),
    source_priority: float = Form(...),
    feed_url: str | None = Form(None),
    fetch_interval_minutes: int | None = Form(None),
    max_items_per_fetch: int | None = Form(None),
    max_item_age_days: int | None = Form(None),
    db: Session = Depends(get_db),
):
    source = db.scalar(select(Source).where(Source.slug == slug))
    if source is None:
        raise HTTPException(404, "source not found")
    if feed_url is not None:
        cleaned_feed_url = feed_url.strip()
        parsed = urlsplit(cleaned_feed_url)
        if cleaned_feed_url and (
            parsed.scheme not in {"http", "https"} or not parsed.hostname
        ):
            raise HTTPException(400, "feed URL must be an absolute HTTP(S) URL")
        if not cleaned_feed_url and source.kind == "rss":
            raise HTTPException(400, "RSS sources require a feed URL")
        source.feed_url = cleaned_feed_url or None
        source.feed_etag = None
        source.feed_last_modified = None
    source.trust_score = max(0.0, min(trust_score, 1.0))
    source.source_priority = max(0.0, min(source_priority, 1.0))
    if fetch_interval_minutes is not None:
        source.fetch_interval_minutes = max(5, min(fetch_interval_minutes, 10080))
    if max_items_per_fetch is not None:
        source.max_items_per_fetch = max(0, min(max_items_per_fetch, 1000))
    if max_item_age_days is not None:
        source.max_item_age_days = max(0, min(max_item_age_days, 3650))
    db.commit()
    db.refresh(source)
    return templates.TemplateResponse(request, "_source_row.html", {"source": source})


@router.post("/sources/{slug}/reset")
def reset_health(slug: str, request: Request, db: Session = Depends(get_db)):
    source = db.scalar(select(Source).where(Source.slug == slug))
    if source is None:
        raise HTTPException(404, "source not found")
    source.active = True
    source.consecutive_failures = 0
    source.last_error_at = None
    db.commit()
    db.refresh(source)
    return templates.TemplateResponse(request, "_source_row.html", {"source": source})
