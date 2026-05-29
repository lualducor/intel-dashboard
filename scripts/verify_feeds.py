"""One-shot feed verifier (PLAN.md §1.9).

Fetches every feed_url in app/sources.yaml and reports OK / FAIL + item count.
Use the report to reconcile sources.yaml: mark broken feeds `active: false` with
a dated comment, or replace the URL, then re-run `python -m scripts.seed_sources`.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import yaml

from app.config import get_settings
from app.services.rss import fetch_rss

SOURCES_PATH = Path(__file__).resolve().parents[1] / "app" / "sources.yaml"


async def _check(entry: dict, settings) -> tuple[str, bool, int, str | None]:
    slug = entry.get("slug", "?")
    feed_url = entry.get("feed_url")
    if not feed_url:
        return (slug, False, 0, "no feed_url")
    try:
        items = await fetch_rss(
            feed_url,
            user_agent=settings.user_agent,
            timeout=settings.http_timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        return (slug, False, 0, f"{type(exc).__name__}: {exc}")
    if not items:
        return (slug, False, 0, "empty feed")
    return (slug, True, len(items), None)


async def main() -> None:
    settings = get_settings()
    entries = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8")) or []
    results = await asyncio.gather(*[_check(e, settings) for e in entries])
    for slug, ok, count, err in results:
        flag = "OK  " if ok else "FAIL"
        print(f"{flag} {slug:22s} items={count:<4} {err or ''}".rstrip())
    broken = [slug for slug, ok, _, _ in results if not ok]
    print(f"\n{len(results) - len(broken)}/{len(results)} feeds OK")
    if broken:
        print("broken (reconcile in sources.yaml):", ", ".join(broken))


if __name__ == "__main__":
    asyncio.run(main())
