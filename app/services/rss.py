from dataclasses import dataclass
from datetime import datetime, timezone
import httpx
import feedparser

@dataclass
class RssItem:
    title: str
    link: str
    summary: str | None
    author: str | None
    published_at: datetime | None   # MUST be timezone-aware UTC, or None
    language: str | None

async def fetch_rss(feed_url: str, *, user_agent: str, timeout: float) -> list[RssItem]:
    headers = {"User-Agent": user_agent}
    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.get(feed_url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        content = resp.content

    parsed = feedparser.parse(content)
    items = []

    for entry in parsed.entries:
        title = entry.get("title", "")
        link = entry.get("link", "")
        
        if not title and not link:
            continue
            
        summary = entry.get("summary") or entry.get("description") or None
        author = entry.get("author") or None
        
        published_at = None
        struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if struct:
            published_at = datetime(*struct[:6], tzinfo=timezone.utc)
            
        language = entry.get("language") or parsed.feed.get("language") or None
        
        items.append(RssItem(
            title=title,
            link=link,
            summary=summary,
            author=author,
            published_at=published_at,
            language=language
        ))
        
    return items
