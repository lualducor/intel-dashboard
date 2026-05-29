"""Daily horoscope fetcher (out-of-band, not part of the RSS ingest path).

The original `horoscope-cancer` RSS feed is dead (empty body), so the horoscope
section never received data. This service pulls the daily Cancer horoscope from a
JSON API instead and upserts a single `topic="horoscope"` Article that the
dashboard's `queues.horoscope_today` query already reads.

A primary API is tried first, then a fallback. One article per (sign, date) is
kept — re-running the same day updates the text in place rather than duplicating.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

import httpx
from sqlalchemy import select

from ..config import Settings, get_settings
from ..db import SessionLocal
from ..models import Article, Source
from . import derive, normalizer, scorer

log = logging.getLogger("intel.horoscope")

SIGN = "cancer"
SOURCE_SLUG = "horoscope-cancer"

_PRIMARY_URL = (
    "https://horoscope-app-api.vercel.app/api/v1/get-horoscope/daily"
    "?sign={sign}&day=today"
)
_FALLBACK_URL = "https://ohmanda.com/api/horoscope/{sign}/"


async def _fetch_text(*, user_agent: str, timeout: float) -> tuple[str, str]:
    """Return (horoscope_text, iso_date). Tries primary API, then fallback."""
    headers = {"User-Agent": user_agent, "Accept": "application/json"}
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        try:
            resp = await client.get(_PRIMARY_URL.format(sign=SIGN), headers=headers)
            resp.raise_for_status()
            data = resp.json()["data"]
            return data["horoscope"].strip(), data.get("date") or date.today().isoformat()
        except Exception as exc:  # noqa: BLE001 — fall through to backup source
            log.warning("primary horoscope API failed (%s), trying fallback", exc)

        resp = await client.get(_FALLBACK_URL.format(sign=SIGN), headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data["horoscope"].strip(), data.get("date") or date.today().isoformat()


def _parse_day(iso_date: str) -> datetime:
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)


def upsert_horoscope(
    db, source: Source, *, text: str, iso_date: str, now: datetime
) -> Article:
    """Insert today's horoscope, or update it in place if already fetched today."""
    dedup = normalizer.dedup_hash(f"horoscope:{SIGN}:{iso_date}")
    title = f"Cancer — {iso_date}"
    published = _parse_day(iso_date)

    article = db.scalar(select(Article).where(Article.dedup_hash == dedup))
    if article is not None:
        article.title = title
        article.summary = text
        article.content_hash = normalizer.content_hash(title, text)
        article.reading_time_minutes = derive.reading_time_minutes(text)
        article.published_at = published
        article.fetched_at = now
        article.last_scored_at = now
        db.commit()
        return article

    article = Article(
        source_id=source.id,
        title=title,
        raw_title=title,
        normalized_title=normalizer.normalized_title(title),
        summary=text,
        original_url=source.url,
        canonical_url=normalizer.canonicalize(source.url),
        dedup_hash=dedup,
        content_hash=normalizer.content_hash(title, text),
        language="en",
        country_scope="global",
        topic="horoscope",
        category="horoscope",
        urgency="normal",
        reading_time_minutes=derive.reading_time_minutes(text),
        published_at=published,
        fetched_at=now,
        scraping_method="api",
        status="new",
        final_score=0.0,
        score_version=scorer.SCORE_VERSION,
        last_scored_at=now,
    )
    db.add(article)
    db.commit()
    return article


async def refresh_horoscope(
    *, settings: Settings | None = None, session_factory=None
) -> dict:
    """Fetch today's Cancer horoscope and upsert it. Safe to call repeatedly."""
    settings = settings or get_settings()
    db = (session_factory or SessionLocal)()
    try:
        source = db.scalar(select(Source).where(Source.slug == SOURCE_SLUG))
        if source is None:
            return {"ok": False, "error": "horoscope source not seeded"}
        try:
            text, iso_date = await _fetch_text(
                user_agent=settings.user_agent,
                timeout=settings.http_timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("horoscope refresh failed: %s", exc)
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}

        now = datetime.now(timezone.utc)
        article = upsert_horoscope(
            db, source, text=text, iso_date=iso_date, now=now
        )
        return {"ok": True, "date": iso_date, "article_id": article.id}
    finally:
        db.close()
