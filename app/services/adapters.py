"""Source adapter registry for RSS/Atom and structured HTML listing pages."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .rss import EmptyFeedError, RssFetchResult, RssItem, fetch_rss, plain_text


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _json_ld_items(soup: BeautifulSoup, base_url: str) -> list[RssItem]:
    items: list[RssItem] = []
    accepted = {"Article", "NewsArticle", "BlogPosting", "TechArticle"}
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        nodes = payload if isinstance(payload, list) else [payload]
        expanded = []
        for node in nodes:
            if isinstance(node, dict) and isinstance(node.get("@graph"), list):
                expanded.extend(node["@graph"])
            else:
                expanded.append(node)
        for node in expanded:
            if not isinstance(node, dict) or node.get("@type") not in accepted:
                continue
            title = str(node.get("headline") or node.get("name") or "").strip()
            raw_url = node.get("url") or node.get("mainEntityOfPage")
            if isinstance(raw_url, dict):
                raw_url = raw_url.get("@id") or raw_url.get("url")
            link = urljoin(base_url, str(raw_url or "").strip())
            if not title or not link:
                continue
            author = node.get("author")
            if isinstance(author, dict):
                author = author.get("name")
            items.append(
                RssItem(
                    title=title,
                    link=link,
                    summary=plain_text(str(node.get("description") or "")),
                    author=str(author).strip() if author else None,
                    published_at=_parse_datetime(
                        str(node.get("datePublished") or node.get("dateModified") or "")
                    ),
                    language=str(node.get("inLanguage") or "").strip() or None,
                )
            )
    return items


def _html_card_items(soup: BeautifulSoup, base_url: str) -> list[RssItem]:
    items: list[RssItem] = []
    cards = soup.select("article")
    if not cards:
        cards = [heading.parent for heading in soup.select("main h2, main h3")]
    for card in cards:
        if card is None:
            continue
        anchor = card.select_one("h1 a[href], h2 a[href], h3 a[href], a[href]")
        heading = card.select_one("h1, h2, h3")
        if anchor is None:
            continue
        title = (heading or anchor).get_text(" ", strip=True)
        link = urljoin(base_url, anchor.get("href", "").strip())
        if not title or not link:
            continue
        paragraph = card.select_one("p")
        time_tag = card.select_one("time")
        items.append(
            RssItem(
                title=title,
                link=link,
                summary=paragraph.get_text(" ", strip=True) if paragraph else None,
                author=None,
                published_at=_parse_datetime(
                    time_tag.get("datetime") if time_tag is not None else None
                ),
                language=None,
            )
        )
    return items


async def fetch_html_listing(
    url: str,
    *,
    user_agent: str,
    timeout: float,
    etag: str | None = None,
    last_modified: str | None = None,
) -> RssFetchResult:
    headers = {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        response = await client.get(url, headers=headers)
    if response.status_code == 304:
        return RssFetchResult([], etag, last_modified, not_modified=True)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    combined = _json_ld_items(soup, str(response.url)) + _html_card_items(
        soup, str(response.url)
    )
    unique: dict[str, RssItem] = {}
    for item in combined:
        unique.setdefault(item.link, item)
    if not unique:
        raise EmptyFeedError("HTML listing contained no structured article links")
    return RssFetchResult(
        list(unique.values()),
        response.headers.get("etag"),
        response.headers.get("last-modified"),
    )


async def fetch_source(source, *, user_agent: str, timeout: float) -> RssFetchResult:
    url = source.feed_url or source.url
    if not url:
        raise ValueError("source has no fetch URL")
    common = {
        "user_agent": user_agent,
        "timeout": timeout,
        "etag": source.feed_etag,
        "last_modified": source.feed_last_modified,
    }
    if source.kind == "rss":
        return await fetch_rss(url, **common)
    if source.kind == "html":
        return await fetch_html_listing(url, **common)
    raise ValueError(f"unsupported source kind: {source.kind}")
