"""Lightweight cross-source story grouping using normalized-title similarity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

from sqlalchemy import func, select

from ..models import Article, StoryCluster

_SIMILARITY_THRESHOLD = 0.84


def _aware_utc(value: datetime) -> datetime:
    """Normalize SQLite's timezone-naive datetime round trips before comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def assign_story_cluster(db, article: Article, *, now: datetime) -> StoryCluster | None:
    candidates = list(
        db.scalars(
            select(Article)
            .where(
                Article.id != article.id,
                Article.topic == article.topic,
                Article.source_id != article.source_id,
                Article.fetched_at >= now - timedelta(days=3),
            )
            .order_by(Article.fetched_at.desc())
            .limit(250)
        )
    )
    match = next(
        (
            candidate
            for candidate in candidates
            if SequenceMatcher(
                None, article.normalized_title, candidate.normalized_title
            ).ratio()
            >= _SIMILARITY_THRESHOLD
        ),
        None,
    )
    if match is None:
        return None

    if match.cluster_id is not None:
        cluster = db.get(StoryCluster, match.cluster_id)
    else:
        match_fetched_at = _aware_utc(match.fetched_at)
        article_fetched_at = _aware_utc(article.fetched_at)
        cluster = StoryCluster(
            representative_title=match.title,
            topic=article.topic,
            first_seen_at=min(match_fetched_at, article_fetched_at),
            last_seen_at=max(match_fetched_at, article_fetched_at),
            source_count=1,
            top_article_id=match.id,
        )
        db.add(cluster)
        db.flush()
        match.cluster_id = cluster.id

    if cluster is None:
        return None
    article.cluster_id = cluster.id
    cluster.last_seen_at = max(
        _aware_utc(cluster.last_seen_at), _aware_utc(article.fetched_at)
    )
    current_top = db.get(Article, cluster.top_article_id) if cluster.top_article_id else None
    if current_top is None or article.final_score > current_top.final_score:
        cluster.top_article_id = article.id
        cluster.representative_title = article.title
    db.flush()
    cluster.source_count = db.scalar(
        select(func.count(func.distinct(Article.source_id))).where(
            Article.cluster_id == cluster.id
        )
    ) or 1
    return cluster
