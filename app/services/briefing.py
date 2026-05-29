from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Article, Briefing
from . import scorer


def generate_briefing(
    db: Session, settings: Settings, *, now: datetime | None = None
) -> Briefing:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=36)

    items = list(
        db.scalars(
            select(Article)
            .where(
                Article.topic == "ai",
                Article.status.in_(("new", "saved", "important")),
                Article.final_score >= settings.threshold_must_read,
                Article.fetched_at >= cutoff,
            )
            .order_by(Article.final_score.desc())
            .limit(5)
        )
    )

    heading = f"# Daily Briefing — {now:%Y-%m-%d %H:%M} UTC\n\n"
    if items:
        body = heading + "\n".join(
            (
                f"{i}. **{article.title}** (score {article.final_score:.2f})\n"
                f"   {article.score_explanation or ''}\n"
                f"   {article.original_url}\n"
            )
            for i, article in enumerate(items, start=1)
        )
    else:
        body = heading + "\n_No must-read items in the last 36h._"

    briefing = Briefing(
        body_markdown=body,
        article_ids_json=json.dumps([article.id for article in items]),
        score_version=scorer.SCORE_VERSION,
    )
    db.add(briefing)
    db.commit()
    db.refresh(briefing)
    return briefing


def get_latest_briefing(db: Session) -> Briefing | None:
    return db.scalars(
        select(Briefing).order_by(Briefing.generated_at.desc()).limit(1)
    ).first()
