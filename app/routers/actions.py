from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Article, ArticleUse, UserAction
from ..templating import templates

router = APIRouter()

ACTION_STATUS = {
    "save": "saved",
    "archive": "archived",
    "useful": "saved",
    "not_relevant": "ignored",
    "important": "important",
    "read": "read",
    "followup": "followup",
    "used_for_content": "used",
}


@router.post("/articles/{article_id}/{action}")
def act(
    article_id: int,
    action: str,
    request: Request,
    use_type: str | None = Form(None),
    content_angle: str | None = Form(None),
    possible_hook: str | None = Form(None),
    related_project: str | None = Form(None),
    db: Session = Depends(get_db),
):
    if action not in ACTION_STATUS:
        raise HTTPException(400, "unknown action")

    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(404)

    article.status = ACTION_STATUS[action]
    db.add(UserAction(article_id=article.id, action=action))

    if action == "used_for_content":
        db.add(
            ArticleUse(
                article_id=article.id,
                use_type=use_type or "personal_reading",
                status="idea",
                content_angle=content_angle,
                possible_hook=possible_hook,
                related_project=related_project,
            )
        )

    db.commit()
    db.refresh(article)

    return templates.TemplateResponse(
        request,
        "_article_card.html",
        {"request": request, "a": article, "settings": get_settings()},
    )
