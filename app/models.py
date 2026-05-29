"""SQLAlchemy ORM models — the full final schema (PLAN.md §4).

All v1 and Phase-8 tables are defined upfront so the initial Alembic migration
is the only schema migration ever needed (no destructive migrations later).
The `articles_fts` FTS5 virtual table and its triggers live in the Alembic
migration, not here (SQLAlchemy ORM does not model virtual tables).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- many-to-many: articles <-> tags (§4.3) ---
article_tags = Table(
    "article_tags",
    Base.metadata,
    Column(
        "article_id",
        ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    feed_url: Mapped[str | None] = mapped_column(String, nullable=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # rss / manual
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    topic: Mapped[str] = mapped_column(String, nullable=False)  # ai / colombia / horoscope
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    source_priority: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    paywalled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    fetch_interval_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60
    )
    default_language: Mapped[str] = mapped_column(String, nullable=False, default="en")
    default_country_scope: Mapped[str] = mapped_column(
        String, nullable=False, default="global"
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    avg_items_per_fetch: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    robots_policy_note: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    articles: Mapped[list[Article]] = relationship(
        back_populates="source", passive_deletes=True
    )
    fetch_logs: Mapped[list[SourceFetchLog]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    raw_title: Mapped[str] = mapped_column(String, nullable=False)
    normalized_title: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_url: Mapped[str] = mapped_column(String, nullable=False)
    canonical_url: Mapped[str] = mapped_column(String, nullable=False)
    dedup_hash: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    language: Mapped[str] = mapped_column(String, nullable=False)
    country_scope: Mapped[str] = mapped_column(String, nullable=False)
    topic: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    urgency: Mapped[str] = mapped_column(String, nullable=False)
    reading_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    cluster_id: Mapped[int | None] = mapped_column(
        ForeignKey("story_clusters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    scraping_method: Mapped[str] = mapped_column(String, nullable=False)  # rss / manual
    paywalled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="new", index=True
    )

    # Scorer breakdown (§6.1)
    source_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    freshness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    keyword_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    category_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    user_feedback_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    novelty_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    final_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    score_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    score_version: Mapped[str] = mapped_column(
        String, nullable=False, default="v1_base", index=True
    )
    last_scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    enriched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    source: Mapped[Source] = relationship(back_populates="articles")
    tags: Mapped[list[Tag]] = relationship(
        secondary=article_tags, back_populates="articles"
    )
    actions: Mapped[list[UserAction]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    notes: Mapped[list[Note]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    score_runs: Mapped[list[ScoreRun]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    uses: Mapped[list[ArticleUse]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    annotations: Mapped[list[AiAnnotation]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    embeddings: Mapped[list[ArticleEmbedding]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_articles_topic_final_score", "topic", text("final_score DESC")),
    )


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    articles: Mapped[list[Article]] = relationship(
        secondary=article_tags, back_populates="tags"
    )


class UserAction(Base):
    __tablename__ = "user_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    article: Mapped[Article] = relationship(back_populates="actions")


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    article: Mapped[Article] = relationship(back_populates="notes")


class Briefing(Base):
    __tablename__ = "briefings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    article_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    score_version: Mapped[str] = mapped_column(String, nullable=False)


class SourceFetchLog(Base):
    __tablename__ = "source_fetch_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    items_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_new: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    source: Mapped[Source] = relationship(back_populates="fetch_logs")


class ScoreRun(Base):
    __tablename__ = "score_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    score_version: Mapped[str] = mapped_column(String, nullable=False)
    source_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    freshness_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    keyword_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    category_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    user_feedback_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    novelty_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    semantic_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # Phase 8
    llm_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # Phase 8
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    article: Mapped[Article] = relationship(back_populates="score_runs")


class ArticleUse(Base):
    __tablename__ = "article_uses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    use_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    content_angle: Mapped[str | None] = mapped_column(Text, nullable=True)
    possible_hook: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_project: Mapped[str | None] = mapped_column(String, nullable=True)
    target_platform: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    article: Mapped[Article] = relationship(back_populates="uses")


class AiAnnotation(Base):
    """Schema only in MVP; rows written in Phase 8."""

    __tablename__ = "ai_annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_name: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String, nullable=False)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    technical_depth_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    content_usefulness_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    novelty_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actionability_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    hype_penalty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    why_relevant: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_angle: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_entities_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    article: Mapped[Article] = relationship(back_populates="annotations")


class ArticleEmbedding(Base):
    """Schema only in MVP; rows written in Phase 8.

    Composite PK (article_id, model_name) allows comparing models.
    """

    __tablename__ = "article_embeddings"

    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    model_name: Mapped[str] = mapped_column(String, primary_key=True)
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    text_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    article: Mapped[Article] = relationship(back_populates="embeddings")


class StoryCluster(Base):
    """Schema only in MVP; rows written in Phase 8."""

    __tablename__ = "story_clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    representative_title: Mapped[str] = mapped_column(String, nullable=False)
    topic: Mapped[str] = mapped_column(String, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Nullable FK back to articles; use_alter avoids the articles<->story_clusters
    # circular dependency at DDL time.
    top_article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL", use_alter=True), nullable=True
    )
