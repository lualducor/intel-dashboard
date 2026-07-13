"""Triage queue assignment (PLAN.md §2.3 / Phase 2.3).

All four queues are DERIVED from articles + article_uses — no extra column.
Queue membership SQL is centralized here so the dashboard route, the /feed
filter partial, and tests all share one source of truth.
"""

from __future__ import annotations

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Article, ArticleUse, Note, Source

QUEUES = ("must_read", "maybe_useful", "for_content", "noise")

SAVED_STATUSES = ("saved", "important", "followup", "used")
SAVED_FILTERS = (
    "all",
    "for_reading",
    "for_content",
    "for_project",
    "for_job",
    "with_notes",
    "by_topic",
    "by_source",
)


def _for_content_exists():
    return exists().where(
        and_(
            ArticleUse.article_id == Article.id,
            ArticleUse.status.in_(["idea", "drafted"]),
        )
    )


def queue_condition(queue: str, settings: Settings):
    """Return the SQLAlchemy boolean condition for a queue (topic='ai')."""
    if queue == "must_read":
        return and_(
            Article.topic == "ai",
            Article.status == "new",
            Article.final_score >= settings.threshold_must_read,
        )
    if queue == "maybe_useful":
        return and_(
            Article.topic == "ai",
            Article.status == "new",
            Article.final_score >= settings.threshold_maybe_useful,
            Article.final_score < settings.threshold_must_read,
        )
    if queue == "for_content":
        return and_(
            Article.topic == "ai",
            Article.status.in_(["saved", "followup", "used"]),
            _for_content_exists(),
        )
    if queue == "noise":
        return and_(
            Article.topic == "ai",
            or_(
                and_(
                    Article.status == "new",
                    Article.final_score < settings.threshold_maybe_useful,
                ),
                Article.status == "ignored",
            ),
        )
    raise ValueError(f"unknown queue: {queue}")


def feed(
    db: Session,
    settings: Settings,
    *,
    queue: str,
    category: str | None = None,
    source: str | None = None,
    min_score: float | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[Article]:
    """Articles for a queue, with optional filter chips (category / source slug / min_score)."""
    conditions = [queue_condition(queue, settings)]
    if category:
        conditions.append(Article.category == category)
    if min_score is not None:
        conditions.append(Article.final_score >= min_score)

    # The id tie-breaker keeps offset pagination stable when score and publication
    # timestamps match (a common case for articles imported in the same batch).
    score_order = (
        Article.final_score.desc(),
        Article.published_at.desc(),
        Article.id.desc(),
    )

    if queue in {"must_read", "maybe_useful"} and source is None:
        # Rank within each source, then order by that rank. This round-robin shape
        # prevents a firehose such as arXiv from occupying every slot while still
        # keeping every article reachable on later pages.
        ranked = (
            select(
                Article.id.label("article_id"),
                func.row_number()
                .over(partition_by=Article.source_id, order_by=score_order)
                .label("source_rank"),
            )
            .where(*conditions)
            .subquery()
        )
        stmt = (
            select(Article)
            .join(ranked, Article.id == ranked.c.article_id)
            .order_by(ranked.c.source_rank.asc(), *score_order)
        )
    else:
        stmt = select(Article).where(*conditions)
        if source:
            stmt = stmt.join(Source, Article.source_id == Source.id).where(
                Source.slug == source
            )
        stmt = stmt.order_by(*score_order)

    if offset:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


def queue_counts(db: Session, settings: Settings) -> dict[str, int]:
    counts = {}
    for queue in QUEUES:
        counts[queue] = db.scalar(
            select(func.count()).select_from(Article).where(queue_condition(queue, settings))
        )
    return counts


def side_panel_colombia(db: Session, *, limit: int = 8) -> list[Article]:
    stmt = (
        select(Article)
        .where(Article.topic == "colombia", Article.status != "ignored")
        .order_by(Article.final_score.desc(), Article.published_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def side_panel_crypto(db: Session, *, limit: int = 6) -> list[Article]:
    stmt = (
        select(Article)
        .where(Article.topic == "crypto", Article.status != "ignored")
        .order_by(Article.published_at.desc(), Article.final_score.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def horoscope_today(db: Session) -> Article | None:
    stmt = (
        select(Article)
        .where(Article.topic == "horoscope")
        .order_by(Article.published_at.desc(), Article.fetched_at.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def _use_type_exists(use_type: str):
    return exists().where(
        and_(ArticleUse.article_id == Article.id, ArticleUse.use_type == use_type)
    )


def saved_articles(
    db: Session,
    *,
    filter: str | None = None,
    topic: str | None = None,
    source: str | None = None,
    limit: int | None = None,
) -> list[Article]:
    """Saved/Archive 'saved' page with the Phase 4.1 filter dropdown."""
    stmt = select(Article).where(Article.status.in_(SAVED_STATUSES))

    if filter == "for_content":
        stmt = stmt.where(
            exists().where(
                and_(
                    ArticleUse.article_id == Article.id,
                    ArticleUse.status.in_(["idea", "drafted", "used"]),
                )
            )
        )
    elif filter == "for_project":
        stmt = stmt.where(_use_type_exists("project_research"))
    elif filter == "for_job":
        stmt = stmt.where(_use_type_exists("job_market"))
    elif filter == "for_reading":
        stmt = stmt.where(_use_type_exists("personal_reading"))
    elif filter == "with_notes":
        stmt = stmt.where(exists().where(Note.article_id == Article.id))

    if topic:
        stmt = stmt.where(Article.topic == topic)
    if source:
        stmt = stmt.join(Source, Article.source_id == Source.id).where(
            Source.slug == source
        )

    if filter == "by_topic":
        stmt = stmt.order_by(Article.topic, Article.final_score.desc())
    elif filter == "by_source":
        stmt = stmt.join(Source, Article.source_id == Source.id).order_by(
            Source.name, Article.final_score.desc()
        )
    else:
        stmt = stmt.order_by(Article.final_score.desc(), Article.published_at.desc())

    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))


def archived_articles(db: Session, *, limit: int | None = None) -> list[Article]:
    stmt = (
        select(Article)
        .where(Article.status == "archived")
        .order_by(Article.final_score.desc(), Article.published_at.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt))
