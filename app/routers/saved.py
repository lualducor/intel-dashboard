from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..services import queues
from ..templating import templates

router = APIRouter()


@router.get("/saved")
def saved(
    request: Request,
    filter: str | None = None,
    topic: str | None = None,
    source: str | None = None,
    db: Session = Depends(get_db),
):
    articles = queues.saved_articles(db, filter=filter, topic=topic, source=source)
    return templates.TemplateResponse(
        request,
        "saved.html",
        {
            "articles": articles,
            "settings": get_settings(),
            "active_filter": filter or "all",
            "filters": queues.SAVED_FILTERS,
        },
    )


@router.get("/archive")
def archive(request: Request, db: Session = Depends(get_db)):
    articles = queues.archived_articles(db)
    return templates.TemplateResponse(
        request,
        "archive.html",
        {"articles": articles, "settings": get_settings()},
    )
