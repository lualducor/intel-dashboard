"""Ingest orchestrator (PLAN.md §1.7 / §2.3).

Pipeline per pass:
  acquire filelock (timeout 0.5s) -> read active sources -> compute feedback maps
  -> for each due source: fetch RSS (outside any DB transaction) -> normalize,
  dedupe, tag, score -> insert article + tags + score_runs in a short transaction
  -> update source health -> write source_fetch_logs row.

Local AI is never in this path. HTTP/parse happen outside transactions.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from ..config import Settings, get_settings
from ..db import SessionLocal
from ..models import Article, ScoreRun, Source, SourceFetchLog, Tag
from . import derive, normalizer, paywall, scorer, tagger
from .feedback import compute_affinity_maps, user_feedback_score
from .lock import Timeout, make_ingest_lock
from .rss import fetch_rss

log = logging.getLogger("intel.ingest")

INTERESTS_PATH = Path(__file__).resolve().parents[1] / "interests.yaml"
_EMA_ALPHA = 0.3
_FAILURE_DEACTIVATE_AT = 5


def _aware_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _is_due(source: Source, now: datetime) -> bool:
    last = _aware_utc(source.last_attempt_at)
    if last is None:
        return True
    interval = timedelta(minutes=source.fetch_interval_minutes)
    factor = 2 ** max(0, source.consecutive_failures - 1)
    return now >= last + interval * factor


def _get_or_create_tags(db, names: list[str]) -> list[Tag]:
    if not names:
        return []
    existing = {t.name: t for t in db.scalars(select(Tag).where(Tag.name.in_(names)))}
    result = []
    for name in names:
        tag = existing.get(name)
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
            existing[name] = tag
        result.append(tag)
    return result


async def run_ingest(
    *,
    slug: str | None = None,
    force: bool = False,
    now: datetime | None = None,
    settings: Settings | None = None,
    session_factory=None,
) -> dict:
    """Run one ingest pass. Returns per-source counts, or a locked marker."""
    settings = settings or get_settings()
    settings.ensure_directories()
    lock = make_ingest_lock(settings)
    try:
        await asyncio.to_thread(lock.acquire, timeout=0.5)
    except Timeout:
        log.info("ingest lock held, skipping")
        return {"locked": True, "skipped": True}
    try:
        return await _run_locked(
            slug=slug,
            force=force,
            now=now,
            settings=settings,
            session_factory=session_factory or SessionLocal,
        )
    finally:
        lock.release()


async def _run_locked(
    *, slug: str | None, force: bool, now: datetime | None, settings: Settings, session_factory
) -> dict:
    now = now or datetime.now(timezone.utc)
    interests = tagger.load_interests(INTERESTS_PATH)
    db = session_factory()
    try:
        # --- reads (one transaction, then commit to close before async fetches) ---
        stmt = select(Source).where(
            Source.active.is_(True),
            Source.kind == "rss",
            Source.feed_url.is_not(None),
        )
        if slug:
            stmt = stmt.where(Source.slug == slug)
        sources = list(db.scalars(stmt))

        maps = compute_affinity_maps(db, now=now)
        recent_titles = list(
            db.scalars(
                select(Article.normalized_title).where(
                    Article.fetched_at >= now - timedelta(hours=24)
                )
            )
        )
        seen_hashes = set(db.scalars(select(Article.dedup_hash)))
        db.commit()

        results = []
        for source in sources:
            if not force and not _is_due(source, now):
                results.append({"slug": source.slug, "skipped": True, "reason": "backoff"})
                continue
            result = await _ingest_source(
                db,
                source,
                interests=interests,
                maps=maps,
                recent_titles=recent_titles,
                seen_hashes=seen_hashes,
                now=now,
                settings=settings,
            )
            results.append(result)

        totals = {
            "items_seen": sum(r.get("items_seen", 0) for r in results),
            "items_new": sum(r.get("items_new", 0) for r in results),
            "sources_run": sum(1 for r in results if not r.get("skipped")),
        }
        return {"locked": False, "sources": results, "totals": totals}
    finally:
        db.close()


async def _ingest_source(
    db,
    source: Source,
    *,
    interests: tagger.Interests,
    maps,
    recent_titles: list[str],
    seen_hashes: set[str],
    now: datetime,
    settings: Settings,
) -> dict:
    started_at = datetime.now(timezone.utc)
    items_seen = 0
    items_new = 0
    error: str | None = None
    try:
        items = await fetch_rss(
            source.feed_url,
            user_agent=settings.user_agent,
            timeout=settings.http_timeout_seconds,
        )
        items_seen = len(items)
        if settings.max_items_per_pass > 0:
            items = items[: settings.max_items_per_pass]

        for item in items:
            canonical = normalizer.canonicalize(item.link)
            dh = normalizer.dedup_hash(canonical)
            if dh in seen_hashes:
                continue
            seen_hashes.add(dh)

            ntitle = normalizer.normalized_title(item.title)
            tags_names, category = tagger.tag_article(
                item.title, item.summary, interests, topic=source.topic
            )
            matched_weights = [w for _, w in tagger.match_buckets(item.title, item.summary, interests)]
            tag_objs = _get_or_create_tags(db, tags_names)

            published_at = item.published_at
            hours_since = (
                (now - published_at).total_seconds() / 3600.0
                if published_at is not None
                else None
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
            sub = scorer.SubScores(ss, fr, kw, cat, fb, nov)
            final = scorer.combine(sub)
            explanation = scorer.build_explanation(
                trust_score=source.trust_score,
                hours_since_published=hours_since,
                tags=tags_names,
                final=final,
            )

            article = Article(
                source_id=source.id,
                title=item.title,
                raw_title=item.title,
                normalized_title=ntitle,
                author=item.author,
                summary=item.summary,
                original_url=item.link,
                canonical_url=canonical,
                dedup_hash=dh,
                content_hash=normalizer.content_hash(item.title, item.summary),
                language=derive.language(source.default_language, item.language),
                country_scope=derive.country_scope(
                    source.default_country_scope, item.title, item.summary
                ),
                topic=source.topic,
                category=category,
                urgency=derive.urgency(
                    item.title, source.source_type, published_at, now=now
                ),
                reading_time_minutes=derive.reading_time_minutes(item.summary),
                published_at=published_at,
                fetched_at=now,
                scraping_method="rss",
                paywalled=paywall.is_paywalled(source.paywalled),
                status="new",
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
            recent_titles.append(ntitle)
            items_new += 1

        # success: reset failures, update health + EMA
        source.consecutive_failures = 0
        source.last_success_at = now
        source.last_attempt_at = now
        if source.avg_items_per_fetch <= 0:
            source.avg_items_per_fetch = float(items_seen)
        else:
            source.avg_items_per_fetch = (
                _EMA_ALPHA * items_seen + (1 - _EMA_ALPHA) * source.avg_items_per_fetch
            )
        db.add(
            SourceFetchLog(
                source_id=source.id,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                ok=True,
                items_seen=items_seen,
                items_new=items_new,
            )
        )
        db.commit()
        return {"slug": source.slug, "ok": True, "items_seen": items_seen, "items_new": items_new}

    except Exception as exc:  # fetch or parse or insert failure
        db.rollback()
        error = f"{type(exc).__name__}: {exc}"[:500]
        source.consecutive_failures += 1
        source.last_attempt_at = now
        source.last_error_at = now
        if source.consecutive_failures >= _FAILURE_DEACTIVATE_AT:
            source.active = False
        db.add(
            SourceFetchLog(
                source_id=source.id,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                ok=False,
                items_seen=items_seen,
                items_new=items_new,
                error=error,
            )
        )
        db.commit()
        log.warning("ingest source %s failed: %s", source.slug, error)
        return {"slug": source.slug, "ok": False, "items_seen": items_seen, "items_new": 0, "error": error}


async def test_source(
    slug: str, *, settings: Settings | None = None, session_factory=None
) -> dict:
    """Fetch + parse a single source WITHOUT persisting (PLAN.md §2.1 test variant)."""
    settings = settings or get_settings()
    db = (session_factory or SessionLocal)()
    try:
        source = db.scalar(select(Source).where(Source.slug == slug))
    finally:
        db.close()
    if source is None:
        return {"ok": False, "error": "unknown source", "items_seen": 0}
    if not source.feed_url:
        return {"ok": False, "error": "no feed_url", "items_seen": 0}
    try:
        items = await fetch_rss(
            source.feed_url,
            user_agent=settings.user_agent,
            timeout=settings.http_timeout_seconds,
        )
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:500], "items_seen": 0}
    last_published = None
    dated = [i.published_at for i in items if i.published_at is not None]
    if dated:
        last_published = max(dated).isoformat()
    return {"ok": True, "items_seen": len(items), "last_published": last_published, "error": None}
