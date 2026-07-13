from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Iterator

import feedparser
import httpx
from bs4 import BeautifulSoup


class EmptyFeedError(ValueError):
    """Raised when an HTTP-successful feed contains no usable entries."""


@dataclass
class RssItem:
    title: str
    link: str
    summary: str | None
    author: str | None
    published_at: datetime | None   # MUST be timezone-aware UTC, or None
    language: str | None


@dataclass
class RssFetchResult:
    items: list[RssItem]
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[RssItem]:
        return iter(self.items)

    def __getitem__(self, index):
        return self.items[index]


def plain_text(value: str | None) -> str | None:
    """Turn publisher-supplied HTML descriptions into compact readable text."""
    if not value:
        return None
    text = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    compact = " ".join(text.split())
    return compact or None


async def fetch_rss(
    feed_url: str,
    *,
    user_agent: str,
    timeout: float,
    etag: str | None = None,
    last_modified: str | None = None,
) -> RssFetchResult:
    headers = {"User-Agent": user_agent}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(feed_url, headers=headers, timeout=timeout)
        if resp.status_code == 304:
            return RssFetchResult(
                items=[],
                etag=etag,
                last_modified=last_modified,
                not_modified=True,
            )
        resp.raise_for_status()
        content = resp.content

    parsed = feedparser.parse(content)
    items: list[RssItem] = []

    for entry in parsed.entries:
        title = entry.get("title", "")
        link = entry.get("link", "")
        
        if not title or not link:
            continue
            
        summary = plain_text(entry.get("summary") or entry.get("description"))
        author = entry.get("author") or None
        
        published_at = None
        struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if struct:
            published_at = datetime(*struct[:6], tzinfo=timezone.utc)
            
        language = entry.get("language") or parsed.feed.get("language") or None
        
        items.append(
            RssItem(
                title=title,
                link=link,
                summary=summary,
                author=author,
                published_at=published_at,
                language=language,
            )
        )

    if not items:
        detail = f": {parsed.bozo_exception}" if parsed.bozo else ""
        raise EmptyFeedError(f"feed contained no usable entries{detail}")

    return RssFetchResult(
        items=items,
        etag=resp.headers.get("etag"),
        last_modified=resp.headers.get("last-modified"),
    )
