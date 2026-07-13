from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Article, Briefing
from . import scorer


def generate_briefing(
    db: Session, settings: Settings, *, now: datetime | None = None
) -> Briefing:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=36)

    score_order = (Article.final_score.desc(), Article.published_at.desc(), Article.id.desc())
    ranked = (
        select(
            Article.id.label("article_id"),
            func.row_number()
            .over(partition_by=Article.source_id, order_by=score_order)
            .label("source_rank"),
        )
        .where(
                Article.topic == "ai",
                Article.status.in_(("new", "saved", "important")),
                Article.final_score >= settings.threshold_must_read,
                Article.fetched_at >= cutoff,
        )
        .subquery()
    )
    items = list(
        db.scalars(
            select(Article)
            .join(ranked, Article.id == ranked.c.article_id)
            .order_by(ranked.c.source_rank.asc(), *score_order)
            .limit(5)
        )
    )

    side_items: dict[str, list[Article]] = {}
    for topic in ("colombia", "crypto"):
        side_items[topic] = list(
            db.scalars(
                select(Article)
                .where(
                    Article.topic == topic,
                    Article.status.not_in(["archived", "ignored"]),
                    Article.fetched_at >= cutoff,
                )
                .order_by(Article.published_at.desc(), Article.final_score.desc())
                .limit(2)
            )
        )

    heading = f"# Daily Briefing — {now:%Y-%m-%d %H:%M} UTC\n\n"
    if items:
        body = heading + "## AI\n\n" + "\n".join(
            (
                f"{i}. **{article.title}** (score {article.final_score:.2f})\n"
                f"   {article.score_explanation or ''}\n"
                f"   {article.original_url}\n"
            )
            for i, article in enumerate(items, start=1)
        )
    else:
        body = heading + "\n_No must-read items in the last 36h._"

    for topic, label in (("colombia", "Colombia / Bogotá"), ("crypto", "Crypto")):
        topic_items = side_items[topic]
        if topic_items:
            body += f"\n\n## {label}\n\n" + "\n".join(
                f"- **{article.title}**\n  {article.original_url}"
                for article in topic_items
            )

    all_items = items + side_items["colombia"] + side_items["crypto"]

    briefing = Briefing(
        body_markdown=body,
        article_ids_json=json.dumps([article.id for article in all_items]),
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
