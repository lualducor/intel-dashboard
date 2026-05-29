from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Article, ArticleUse
from ..templating import templates

router = APIRouter()

@router.get("/content")
def content_page(request: Request, db: Session = Depends(get_db)):
    # Query all ArticleUse rows joined to their Article
    stmt = (
        select(ArticleUse, Article)
        .join(Article, ArticleUse.article_id == Article.id)
        .order_by(ArticleUse.use_type, ArticleUse.status)
    )
    results = db.execute(stmt).all()

    # Group into a dict: {use_type: [ {use, article} ... ]}
    groups = {}
    for use, article in results:
        if use.use_type not in groups:
            groups[use.use_type] = []
        groups[use.use_type].append({"use": use, "article": article})

    status_ladder = ["idea", "drafted", "used", "discarded"]
    return templates.TemplateResponse(
        request,
        "content.html",
        {
            "groups": groups,
            "status_ladder": status_ladder,
        },
    )

@router.post("/content/use/{article_id}")
def upsert_use(
    article_id: int,
    request: Request,
    use_type: str = Form(...),
    status: str = Form("idea"),
    content_angle: str | None = Form(None),
    possible_hook: str | None = Form(None),
    related_project: str | None = Form(None),
    db: Session = Depends(get_db),
):
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    # Find an existing ArticleUse for (article_id, use_type)
    stmt = select(ArticleUse).where(
        ArticleUse.article_id == article_id, ArticleUse.use_type == use_type
    )
    use = db.execute(stmt).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if use:
        # Update existing
        use.status = status
        use.content_angle = content_angle
        use.possible_hook = possible_hook
        use.related_project = related_project
        use.updated_at = now
    else:
        # Create new
        use = ArticleUse(
            article_id=article_id,
            use_type=use_type,
            status=status,
            content_angle=content_angle,
            possible_hook=possible_hook,
            related_project=related_project,
            created_at=now,
        )
        db.add(use)

    db.commit()

    # Return a tiny HTMLResponse
    return HTMLResponse(
        content=f'<span class="use-status" data-status="{status}">{use_type}: {status}</span>'
    )
