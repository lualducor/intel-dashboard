"""Idempotent source seeder (PLAN.md §1.8).

Upserts app/sources.yaml into the sources table by slug. Static config fields
are (re)applied on every run; runtime health columns (last_*, consecutive_failures,
avg_items_per_fetch) are left untouched.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Source

SOURCES_PATH = Path(__file__).resolve().parents[1] / "app" / "sources.yaml"

_DEFAULTS = {
    "feed_url": None,
    "kind": "rss",
    "trust_score": 0.5,
    "source_priority": 0.5,
    "paywalled": False,
    "active": True,
    "fetch_interval_minutes": 60,
    "max_items_per_fetch": 50,
    "max_item_age_days": 90,
    "default_language": "en",
    "default_country_scope": "global",
}


def _fields(entry: dict) -> dict:
    out = {
        "name": entry["name"],
        "url": entry["url"],
        "source_type": entry["source_type"],
        "topic": entry["topic"],
    }
    for key, default in _DEFAULTS.items():
        out[key] = entry.get(key, default)
    return out


def seed(path: Path = SOURCES_PATH, *, session_factory=SessionLocal) -> dict:
    entries = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    db = session_factory()
    created = updated = 0
    try:
        for entry in entries:
            slug = entry["slug"]
            src = db.scalar(select(Source).where(Source.slug == slug))
            fields = _fields(entry)
            if src is None:
                db.add(Source(slug=slug, **fields))
                created += 1
            else:
                for key, value in fields.items():
                    setattr(src, key, value)
                updated += 1
        db.commit()
    finally:
        db.close()
    return {"created": created, "updated": updated, "total": created + updated}


if __name__ == "__main__":
    result = seed()
    print(
        f"seeded sources: created={result['created']} "
        f"updated={result['updated']} total={result['total']}"
    )
