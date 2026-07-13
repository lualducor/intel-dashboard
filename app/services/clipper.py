"""Manual article clipper (PLAN.md §5.2 / Phase 5.2).

Downloads a URL, extracts title/summary (via app.services.extractor), then runs
the SAME deterministic tag+score pipeline as ingest and inserts one article with
scraping_method='manual' under a 'manual-clip' pseudo-source.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..models import Article, ArticleUse, ScoreRun, Source, Tag
from . import derive, extractor, normalizer, scorer, tagger
from .feedback import compute_affinity_maps, user_feedback_score

INTERESTS_PATH = Path(__file__).resolve().parents[1] / "interests.yaml"
MANUAL_SLUG = "manual-clip"


def ensure_manual_source(db: Session) -> Source:
    src = db.scalar(select(Source).where(Source.slug == MANUAL_SLUG))
    if src is None:
        src = Source(
            slug=MANUAL_SLUG,
            name="Manual Clip",
            url="",
            feed_url=None,
            kind="manual",
            source_type="manual_clip",
            topic="ai",
            trust_score=0.5,
            source_priority=0.5,
            default_language="en",
            default_country_scope="global",
            active=True,
        )
        db.add(src)
        db.flush()
    return src


def _get_or_create_tags(db: Session, names: list[str]) -> list[Tag]:
    if not names:
        return []
    existing = {t.name: t for t in db.scalars(select(Tag).where(Tag.name.in_(names)))}
    out = []
    for name in names:
        tag = existing.get(name)
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
            existing[name] = tag
        out.append(tag)
    return out


def clip_url(
    db: Session,
    url: str,
    *,
    settings: Settings | None = None,
    use_type: str | None = None,
    content_angle: str | None = None,
    now: datetime | None = None,
) -> Article:
    settings = settings or get_settings()
    now = now or datetime.now(timezone.utc)
    interests = tagger.load_interests(INTERESTS_PATH)

    source = ensure_manual_source(db)
    canonical = normalizer.canonicalize(url)
    dh = normalizer.dedup_hash(canonical)

    existing = db.scalar(select(Article).where(Article.dedup_hash == dh))
    if existing is not None:
        return existing

    ex = extractor.extract(
        url, user_agent=settings.user_agent, timeout=settings.http_timeout_seconds
    )
    title = ex.title or url
    summary = ex.summary or (ex.text[:1000] if ex.text else None)

    ntitle = normalizer.normalized_title(title)
    tags_names, category = tagger.tag_article(title, summary, interests, topic="ai")
    matched_weights = [
        w
        for _, w in tagger.match_buckets(title, summary, interests, topic="ai")
    ]
    tag_objs = _get_or_create_tags(db, tags_names)

    recent_titles = list(
        db.scalars(
            select(Article.normalized_title).where(
                Article.fetched_at >= now - timedelta(hours=24)
            )
        )
    )
    maps = compute_affinity_maps(db, now=now)

    published_at = ex.published_at
    hours_since = (
        (now - published_at).total_seconds() / 3600.0 if published_at else None
    )
    ss = scorer.source_score(source.trust_score, source.source_priority)
    fr = scorer.freshness_score(published_at, now)
    kw = scorer.keyword_score(matched_weights)
    cat = scorer.category_score(category, interests.categories_priority)
    fb = user_feedback_score(
        source_id=source.id,
        tag_ids=[t.id for t in tag_objs],
        category=category,
        maps=maps,
        cold_floor=settings.feedback_cold_floor,
        ramp_at=settings.feedback_ramp_at_actions,
    )
    nov = scorer.novelty_score(ntitle, recent_titles)
    final = scorer.combine(scorer.SubScores(ss, fr, kw, cat, fb, nov))
    explanation = scorer.build_explanation(
        trust_score=source.trust_score,
        hours_since_published=hours_since,
        tags=tags_names,
        final=final,
    )

    article = Article(
        source_id=source.id,
        title=title,
        raw_title=title,
        normalized_title=ntitle,
        author=ex.author,
        summary=summary,
        original_url=url,
        canonical_url=canonical,
        dedup_hash=dh,
        content_hash=normalizer.content_hash(title, summary),
        language=derive.language(source.default_language, ex.language),
        country_scope=derive.country_scope(source.default_country_scope, title, summary),
        topic="ai",
        category=category,
        urgency=derive.urgency(title, source.source_type, published_at, now=now),
        reading_time_minutes=derive.reading_time_minutes(summary),
        published_at=published_at,
        fetched_at=now,
        scraping_method="manual",
        paywalled=False,
        status="saved",
        source_score=ss,
        freshness_score=fr,
        keyword_score=kw,
        category_score=cat,
        user_feedback_score=fb,
        novelty_score=nov,
        final_score=final,
        score_explanation=explanation,
        score_version=scorer.SCORE_VERSION,
        last_scored_at=now,
    )
    article.tags = tag_objs
    db.add(article)
    db.flush()
    db.add(
        ScoreRun(
            article_id=article.id,
            score_version=scorer.SCORE_VERSION,
            source_score=ss,
            freshness_score=fr,
            keyword_score=kw,
            category_score=cat,
            user_feedback_score=fb,
            novelty_score=nov,
            final_score=final,
            explanation=explanation,
        )
    )
    if use_type:
        db.add(
            ArticleUse(
                article_id=article.id,
                use_type=use_type,
                status="idea",
                content_angle=content_angle,
            )
        )
    db.commit()
    db.refresh(article)
    return article
