"""Recalculate article scores (PLAN.md §6.3 / Phase 6.6).

Re-derives final_score for matching articles using the CURRENT interests.yaml +
feedback history, updates the article (sub-scores, tags, category, explanation)
and appends a score_runs row. --dry-run prints diffs without writing.

    python -m scripts.recalculate_scores [--all | --since 7d | --score-version v1_base]
        [--only-topic ai] [--dry-run]

Novelty note: novelty is re-sampled from the current recent-24h title set, so
historical novelty values may shift on recalc (documented behavior, §6.3).
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import Article, ScoreRun, Tag
from app.services import normalizer, scorer, tagger
from app.services.feedback import compute_affinity_maps, user_feedback_score

INTERESTS_PATH = Path(__file__).resolve().parents[1] / "app" / "interests.yaml"

_DURATION_RE = re.compile(r"^(\d+)([dhm])$")


def _aware_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def parse_duration(text: str) -> timedelta:
    m = _DURATION_RE.match(text.strip())
    if not m:
        raise ValueError(f"bad duration {text!r} (use e.g. 7d, 24h, 30m)")
    n, unit = int(m.group(1)), m.group(2)
    return {"d": timedelta(days=n), "h": timedelta(hours=n), "m": timedelta(minutes=n)}[unit]


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


def recalculate(
    *,
    session_factory=SessionLocal,
    all: bool = False,
    since: str | None = None,
    score_version: str | None = None,
    only_topic: str | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
) -> dict:
    settings = get_settings()
    now = now or datetime.now(timezone.utc)
    interests = tagger.load_interests(INTERESTS_PATH)
    db = session_factory()
    try:
        stmt = select(Article)
        if since:
            stmt = stmt.where(Article.fetched_at >= now - parse_duration(since))
        if score_version:
            stmt = stmt.where(Article.score_version == score_version)
        if only_topic:
            stmt = stmt.where(Article.topic == only_topic)
        if not (all or since or score_version or only_topic):
            raise ValueError("specify --all, --since, --score-version, or --only-topic")

        articles = list(db.scalars(stmt))
        maps = compute_affinity_maps(db, now=now)
        recent_titles = list(
            db.scalars(
                select(Article.normalized_title).where(
                    Article.fetched_at >= now - timedelta(hours=24)
                )
            )
        )

        diffs = []
        changed = 0
        for a in articles:
            tags_names, category = tagger.tag_article(
                a.title, a.summary, interests, topic=a.topic
            )
            tag_objs = _get_or_create_tags(db, tags_names)
            matched_weights = [
                w
                for _, w in tagger.match_buckets(
                    a.title, a.summary, interests, topic=a.topic
                )
            ]
            published_at = _aware_utc(a.published_at)
            hours_since = (
                (now - published_at).total_seconds() / 3600.0 if published_at else None
            )
            ss = scorer.source_score(a.source.trust_score, a.source.source_priority)
            fr = scorer.freshness_score(published_at, now)
            kw = scorer.keyword_score(matched_weights)
            cat = scorer.category_score(category, interests.categories_priority)
            fb = user_feedback_score(
                source_id=a.source_id,
                tag_ids=[t.id for t in tag_objs],
                category=category,
                maps=maps,
                cold_floor=settings.feedback_cold_floor,
                ramp_at=settings.feedback_ramp_at_actions,
            )
            nov = scorer.novelty_score(a.normalized_title, recent_titles)
            new_final = scorer.combine(scorer.SubScores(ss, fr, kw, cat, fb, nov))
            explanation = scorer.build_explanation(
                trust_score=a.source.trust_score,
                hours_since_published=hours_since,
                tags=tags_names,
                final=new_final,
            )
            if abs(new_final - a.final_score) > 1e-9:
                changed += 1
                diffs.append((a.id, round(a.final_score, 4), round(new_final, 4)))

            if not dry_run:
                a.source_score = ss
                a.freshness_score = fr
                a.keyword_score = kw
                a.category_score = cat
                a.user_feedback_score = fb
                a.novelty_score = nov
                a.final_score = new_final
                a.category = category
                a.score_explanation = explanation
                a.last_scored_at = now
                a.tags = tag_objs
                db.add(
                    ScoreRun(
                        article_id=a.id,
                        score_version=scorer.SCORE_VERSION,
                        source_score=ss,
                        freshness_score=fr,
                        keyword_score=kw,
                        category_score=cat,
                        user_feedback_score=fb,
                        novelty_score=nov,
                        final_score=new_final,
                        explanation=explanation,
                    )
                )

        if dry_run:
            db.rollback()
        else:
            db.commit()
        return {"matched": len(articles), "changed": changed, "dry_run": dry_run, "diffs": diffs}
    finally:
        db.close()


def rescore_article_by_id(
    db: Session, article_id: int, *, settings=None, now: datetime | None = None
) -> dict | None:
    """Recompute one article's score within the caller's session (does NOT commit).

    Used by the score-debug 'recalculate this article' button. Returns
    {"old": float, "new": float} or None if the article does not exist.
    """
    settings = settings or get_settings()
    now = now or datetime.now(timezone.utc)
    interests = tagger.load_interests(INTERESTS_PATH)

    a = db.get(Article, article_id)
    if a is None:
        return None

    maps = compute_affinity_maps(db, now=now)
    recent_titles = list(
        db.scalars(
            select(Article.normalized_title).where(
                Article.fetched_at >= now - timedelta(hours=24)
            )
        )
    )
    tags_names, category = tagger.tag_article(
        a.title, a.summary, interests, topic=a.topic
    )
    tag_objs = _get_or_create_tags(db, tags_names)
    matched_weights = [
        w
        for _, w in tagger.match_buckets(
            a.title, a.summary, interests, topic=a.topic
        )
    ]
    published_at = _aware_utc(a.published_at)
    hours_since = (
        (now - published_at).total_seconds() / 3600.0 if published_at else None
    )
    ss = scorer.source_score(a.source.trust_score, a.source.source_priority)
    fr = scorer.freshness_score(published_at, now)
    kw = scorer.keyword_score(matched_weights)
    cat = scorer.category_score(category, interests.categories_priority)
    fb = user_feedback_score(
        source_id=a.source_id,
        tag_ids=[t.id for t in tag_objs],
        category=category,
        maps=maps,
        cold_floor=settings.feedback_cold_floor,
        ramp_at=settings.feedback_ramp_at_actions,
    )
    nov = scorer.novelty_score(a.normalized_title, recent_titles)
    new_final = scorer.combine(scorer.SubScores(ss, fr, kw, cat, fb, nov))
    explanation = scorer.build_explanation(
        trust_score=a.source.trust_score,
        hours_since_published=hours_since,
        tags=tags_names,
        final=new_final,
    )
    old_final = a.final_score
    a.source_score, a.freshness_score, a.keyword_score = ss, fr, kw
    a.category_score, a.user_feedback_score, a.novelty_score = cat, fb, nov
    a.final_score = new_final
    a.category = category
    a.score_explanation = explanation
    a.last_scored_at = now
    a.tags = tag_objs
    db.add(
        ScoreRun(
            article_id=a.id,
            score_version=scorer.SCORE_VERSION,
            source_score=ss,
            freshness_score=fr,
            keyword_score=kw,
            category_score=cat,
            user_feedback_score=fb,
            novelty_score=nov,
            final_score=new_final,
            explanation=explanation,
        )
    )
    return {"old": old_final, "new": new_final}


def main() -> None:
    p = argparse.ArgumentParser(description="Recalculate article scores")
    p.add_argument("--all", action="store_true")
    p.add_argument("--since", default=None, help="e.g. 7d / 24h / 30m")
    p.add_argument("--score-version", default=None)
    p.add_argument("--only-topic", default=None)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    result = recalculate(
        all=args.all,
        since=args.since,
        score_version=args.score_version,
        only_topic=args.only_topic,
        dry_run=args.dry_run,
    )
    tag = "DRY-RUN" if result["dry_run"] else "APPLIED"
    print(f"[{tag}] matched={result['matched']} changed={result['changed']}")
    for aid, old, new in result["diffs"][:50]:
        print(f"  article {aid}: {old} -> {new}")


if __name__ == "__main__":
    main()
