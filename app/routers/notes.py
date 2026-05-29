from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Article, Note
from ..templating import templates

router = APIRouter()


@router.post("/articles/{article_id}/notes")
def add_note(
    article_id: int,
    request: Request,
    body: str = Form(...),
    db: Session = Depends(get_db),
):
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(404)

    db.add(Note(article_id=article.id, body=body))
    db.commit()
    db.refresh(article)

    return templates.TemplateResponse(
        request,
        "_article_card.html",
        {"request": request, "a": article, "settings": get_settings()},
    )
