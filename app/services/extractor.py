from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import trafilatura
from bs4 import BeautifulSoup


@dataclass
class Extracted:
    title: str
    summary: str | None
    text: str | None
    author: str | None
    published_at: datetime | None
    language: str | None


def extract(url: str, *, user_agent: str, timeout: float) -> Extracted:
    """Download and extract article content and metadata."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            return Extracted("", None, None, None, None, None)

        text = (
            trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            or None
        )
        meta = trafilatura.extract_metadata(downloaded)

        title = ""
        author = None
        published_at = None
        language = None
        summary = None

        if meta:
            title = meta.title or ""
            author = meta.author or None
            language = getattr(meta, "language", None) or None
            summary = meta.description or None
            if meta.date:
                try:
                    # Try ISO first, then Y-m-d
                    try:
                        dt = datetime.fromisoformat(meta.date)
                    except ValueError:
                        dt = datetime.strptime(meta.date, "%Y-%m-%d")

                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.astimezone(timezone.utc)
                    published_at = dt
                except (ValueError, TypeError, OverflowError):
                    published_at = None

        # Fallback for title
        if not title:
            soup = BeautifulSoup(downloaded, "html.parser")
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)
            if not title:
                og_title = soup.find("meta", property="og:title")
                if og_title:
                    title = og_title.get("content", "").strip()

        # Fallback for summary
        if not summary and text:
            summary = text[:500]

        return Extracted(
            title=title,
            summary=summary,
            text=text,
            author=author,
            published_at=published_at,
            language=language,
        )
    except Exception:
        return Extracted("", None, None, None, None, None)
