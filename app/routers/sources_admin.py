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
    db: Session = Depends(get_db),
):
    source = db.scalar(select(Source).where(Source.slug == slug))
    if source is None:
        raise HTTPException(404, "source not found")
    source.trust_score = trust_score
    source.source_priority = source_priority
    db.commit()
    db.refresh(source)
    return templates.TemplateResponse(request, "_source_row.html", {"source": source})
