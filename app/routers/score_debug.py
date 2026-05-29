from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Article, ScoreRun
from ..services import scorer
from ..templating import templates
from scripts.recalculate_scores import rescore_article_by_id

router = APIRouter()

@router.get("/debug/scoring/{article_id}")
def score_debug(article_id: int, request: Request, db: Session = Depends(get_db)):
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(404)
    runs = db.scalars(
        select(ScoreRun)
        .where(ScoreRun.article_id == article_id)
        .order_by(ScoreRun.created_at)
    ).all()
    # diffs between consecutive runs: list of dicts {field: (prev, cur)} for final_score + each sub-score
    diffs = []
    for prev, cur in zip(runs, runs[1:]):
        diffs.append({
            "from_id": prev.id,
            "to_id": cur.id,
            "final": (round(prev.final_score, 4), round(cur.final_score, 4))
        })
    return templates.TemplateResponse(
        request,
        "score_debug.html",
        {"article": article, "weights": scorer.WEIGHTS, "runs": runs, "diffs": diffs}
    )

@router.post("/debug/scoring/{article_id}/recalc")
def recalc(article_id: int, db: Session = Depends(get_db)):
    result = rescore_article_by_id(db, article_id)
    if result is None:
        raise HTTPException(404)
    db.commit()
    return RedirectResponse(url=f"/debug/scoring/{article_id}", status_code=303)
