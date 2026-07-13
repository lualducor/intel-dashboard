"""Source adapters for RSS/Atom, generic HTML, and known publisher layouts."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from .rss import EmptyFeedError, RssFetchResult, RssItem, fetch_rss, plain_text

_ENGLISH_DATE_RE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s+\d{1,2},\s+\d{4}\b",
    re.IGNORECASE,
)
_URL_DATE_RE = re.compile(r"/(20\d{2})/(\d{2})/(\d{2})/")
_RADWARE_MIRROR_ITEM_RE = re.compile(
    r"\[!\[Image \d+: (?P<title>[^\]]+)\]\([^)]+\)"
    r"(?P<body>.*?)\*\*\|\*\*(?P<date>"
    r"(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{1,2},\s+20\d{2})\]"
    r"\((?P<link>https://www\.radware\.com/blog/posts/[^)]+)\)",
    re.DOTALL,
)
_YAHOO_STORY_RE = re.compile(
    r'"canonicalUrl":"(?P<link>https://tech\.yahoo\.com/[^"\\]+/article/[^"\\]+)"'
    r'[^{}]{0,1000}?"displayTime":"(?P<date>[^"\\]+)"'
    r'[^{}]{0,1000}?"headline":"(?P<title>(?:\\.|[^"\\])*)"'
)
_SPANISH_MONTHS = {
    "ene": 1,
    "enero": 1,
    "feb": 2,
    "febrero": 2,
    "mar": 3,
    "marzo": 3,
    "abr": 4,
    "abril": 4,
    "may": 5,
    "mayo": 5,
    "jun": 6,
    "junio": 6,
    "jul": 7,
    "julio": 7,
    "ago": 8,
    "agosto": 8,
    "sep": 9,
    "septiembre": 9,
    "oct": 10,
    "octubre": 10,
    "nov": 11,
    "noviembre": 11,
    "dic": 12,
    "diciembre": 12,
}


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


def _parse_date_text(value: str | None) -> datetime | None:
    if not value:
        return None
    compact = " ".join(value.replace("•", " ").split())
    parsed = _parse_datetime(compact)
    if parsed is not None:
        return parsed
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(compact, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    spanish = compact.casefold().replace(" de ", " ").split()
    if len(spanish) == 3 and spanish[1] in _SPANISH_MONTHS:
        try:
            return datetime(
                int(spanish[2]),
                _SPANISH_MONTHS[spanish[1]],
                int(spanish[0]),
                tzinfo=timezone.utc,
            )
        except ValueError:
            return None
    return None


def _longest_text(elements, *, minimum: int = 1) -> str | None:
    values = [element.get_text(" ", strip=True) for element in elements]
    usable = [value for value in values if len(value) >= minimum]
    return max(usable, key=len) if usable else None


def _summary_from(container) -> str | None:
    return _longest_text(container.select("p"), minimum=20)


def _anthropic_items(soup: BeautifulSoup, base_url: str) -> list[RssItem]:
    items = []
    for anchor in soup.select('a[href^="/news/"], a[href^="https://www.anthropic.com/news/"]'):
        link = urljoin(base_url, anchor.get("href", "").strip())
        if urlsplit(link).path.rstrip("/") == "/news":
            continue
        title = _longest_text(
            anchor.select("h1, h2, h3, h4, [class*='title'], [class*='Title']"),
            minimum=8,
        )
        time_tag = anchor.select_one("time")
        if not title or time_tag is None:
            continue
        items.append(
            RssItem(
                title=title,
                link=link,
                summary=_summary_from(anchor),
                author="Anthropic",
                published_at=_parse_date_text(
                    time_tag.get("datetime") or time_tag.get_text(" ", strip=True)
                ),
                language="en",
            )
        )
    return items


def _mintic_items(soup: BeautifulSoup, base_url: str) -> list[RssItem]:
    items = []
    for card in soup.select(".recuadro"):
        anchor = card.select_one('a[href*="/Sala-de-prensa/Noticias/"]')
        date = card.select_one(".fecha")
        if anchor is None or date is None:
            continue
        title = anchor.get_text(" ", strip=True)
        link = urljoin(base_url, anchor.get("href", "").strip())
        if not title or not link:
            continue
        items.append(
            RssItem(
                title=title,
                link=link,
                summary=None,
                author="Ministerio TIC",
                published_at=_parse_date_text(date.get_text(" ", strip=True)),
                language="es",
            )
        )
    return items


def _meta_items(soup: BeautifulSoup, base_url: str) -> list[RssItem]:
    grouped: dict[str, list] = {}
    for anchor in soup.select('a[href*="/blog/"]'):
        link = urljoin(base_url, anchor.get("href", "").strip())
        parsed = urlsplit(link)
        if parsed.hostname not in {"ai.meta.com", "www.ai.meta.com"}:
            continue
        if parsed.path.rstrip("/") == "/blog" or not parsed.path.startswith("/blog/"):
            continue
        grouped.setdefault(link, []).append(anchor)

    items = []
    for link, anchors in grouped.items():
        containers = []
        for anchor in anchors:
            for parent in list(anchor.parents)[:8]:
                text = parent.get_text(" ", strip=True)
                if _ENGLISH_DATE_RE.search(text) and parent.select("h1, h2, h3, h4"):
                    containers.append(parent)
                    break
        if not containers:
            continue
        container = min(containers, key=lambda element: len(element.get_text(" ", strip=True)))
        title_candidates = list(container.select("h1, h2, h3, h4")) + anchors
        title_values = [element.get_text(" ", strip=True) for element in title_candidates]
        title_values = [
            value
            for value in title_values
            if len(value) >= 8 and value.casefold() not in {"learn more", "más información"}
        ]
        match = _ENGLISH_DATE_RE.search(container.get_text(" ", strip=True))
        if not title_values or match is None:
            continue
        items.append(
            RssItem(
                title=max(title_values, key=len),
                link=link,
                summary=_summary_from(container),
                author="Meta AI",
                published_at=_parse_date_text(match.group(0)),
                language="en",
            )
        )
    return items


def _bogota_items(soup: BeautifulSoup, base_url: str) -> list[RssItem]:
    items = []
    for card in soup.select(".tarjeta.tarjeta-3"):
        anchor = card.select_one("h2 a[href]")
        date = card.select_one(".views-field-created")
        if anchor is None or date is None:
            continue
        title = anchor.get_text(" ", strip=True)
        link = urljoin(base_url, anchor.get("href", "").strip())
        if not title or not link:
            continue
        items.append(
            RssItem(
                title=title,
                link=link,
                summary=_summary_from(card),
                author="Portal Bogotá",
                published_at=_parse_date_text(date.get_text(" ", strip=True)),
                language="es",
            )
        )
    return items


def _microsoft_ai_items(soup: BeautifulSoup, base_url: str) -> list[RssItem]:
    items = []
    for card in soup.select("article"):
        if card.select_one('a[href*="/tag/ai/"]') is None:
            continue
        anchor = card.select_one("h1 a[href], h2 a[href], h3 a[href]")
        if anchor is None:
            continue
        title = anchor.get_text(" ", strip=True)
        link = urljoin(base_url, anchor.get("href", "").strip())
        if not title or not link:
            continue
        match = _URL_DATE_RE.search(urlsplit(link).path)
        published_at = (
            datetime(*(int(part) for part in match.groups()), tzinfo=timezone.utc)
            if match
            else None
        )
        items.append(
            RssItem(
                title=title,
                link=link,
                summary=_summary_from(card),
                author="Microsoft",
                published_at=published_at,
                language="en",
            )
        )
    return items


def _afr_technology_items(soup: BeautifulSoup, base_url: str) -> list[RssItem]:
    items = []
    for anchor in soup.select('h3 a[href^="/technology/"]'):
        card = anchor.find_parent(attrs={"data-testid": "StoryTileBase"})
        if card is None:
            continue
        title = anchor.get_text(" ", strip=True)
        link = urljoin(base_url, anchor.get("href", "").strip())
        if not title or not link:
            continue
        summary = card.select_one('[data-pb-type="ab"]')
        time_tag = card.select_one("time")
        author = card.select_one('[data-pb-type="au"]')
        items.append(
            RssItem(
                title=title,
                link=link,
                summary=summary.get_text(" ", strip=True) if summary else None,
                author=author.get_text(" ", strip=True) if author else None,
                published_at=(
                    _parse_date_text(time_tag.get("datetime"))
                    or _parse_date_text(time_tag.get_text(" ", strip=True))
                    if time_tag
                    else None
                ),
                language="en",
            )
        )
    return items


def _radware_mirror_items(soup: BeautifulSoup, _base_url: str) -> list[RssItem]:
    """Parse Radware's listing through its read-only text mirror.

    Radware challenges non-browser clients before serving both its listing and
    RSS endpoint. The mirror preserves canonical Radware links and publication
    dates, so the dashboard never stores mirror URLs as article destinations.
    """
    text = soup.get_text("\n")
    items = []
    for match in _RADWARE_MIRROR_ITEM_RE.finditer(text):
        body = " ".join(match.group("body").replace("**", " ").split())
        title = match.group("title").strip()
        title_position = body.find(title)
        summary = body[title_position + len(title) :].strip() if title_position >= 0 else body
        items.append(
            RssItem(
                title=title,
                link=match.group("link"),
                summary=summary or None,
                author="Radware",
                published_at=_parse_date_text(match.group("date")),
                language="en",
            )
        )
    return items


def _yahoo_tech_items(soup: BeautifulSoup, _base_url: str) -> list[RssItem]:
    items = []
    for script in soup.select("script"):
        payload = (script.string or "").replace('\\"', '"')
        for match in _YAHOO_STORY_RE.finditer(payload):
            try:
                title = json.loads(f'"{match.group("title")}"')
            except json.JSONDecodeError:
                title = match.group("title")
            items.append(
                RssItem(
                    title=title.strip(),
                    link=match.group("link"),
                    summary=None,
                    author="Yahoo Tech",
                    published_at=_parse_datetime(match.group("date")),
                    language="en",
                )
            )
    return items


_SITE_PARSERS = {
    "anthropic.com": _anthropic_items,
    "mintic.gov.co": _mintic_items,
    "ai.meta.com": _meta_items,
    "bogota.gov.co": _bogota_items,
    "news.microsoft.com": _microsoft_ai_items,
    "afr.com": _afr_technology_items,
    "r.jina.ai": _radware_mirror_items,
    "tech.yahoo.com": _yahoo_tech_items,
}


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
    response_url = str(response.url)
    hostname = (urlsplit(response_url).hostname or "").removeprefix("www.")
    site_parser = _SITE_PARSERS.get(hostname)
    if site_parser is None:
        combined = _json_ld_items(soup, response_url) + _html_card_items(soup, response_url)
    else:
        combined = site_parser(soup, response_url)
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
