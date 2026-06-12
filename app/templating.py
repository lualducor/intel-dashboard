"""Shared Jinja2 templates instance.

Lives in its own module so routers can import `templates` without importing
app.main (which would create a circular import).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from fastapi.templating import Jinja2Templates

from .config import get_settings

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

PAYWALLED_DOMAINS = {
    "eltiempo.com",
    "www.eltiempo.com",
}


def to_bogota_local(dt: datetime | None, settings=None):
    if dt is None:
        return None
    if settings is None:
        settings = get_settings()
    if dt.tzinfo is not None:
        return dt.astimezone(ZoneInfo(settings.display_tz))
    return dt


def _url_is_paywalled(url: str) -> bool:
    if not url:
        return False
    host = urlsplit(url).hostname or ""
    return host.lower() in PAYWALLED_DOMAINS


def paywall_url(article, settings=None) -> str:
    """Return the article link, prefixed with the paywall proxy when needed.

    Treats an article as paywalled if its `paywalled` flag is set OR its URL
    host matches a known paywalled domain (e.g. eltiempo.com surfaced via an
    aggregator source).
    """
    url = getattr(article, "original_url", "") or ""
    if not url:
        return url
    if settings is None:
        settings = get_settings()
    paywalled = bool(getattr(article, "paywalled", False)) or _url_is_paywalled(url)
    if paywalled and settings.paywall_proxy_prefix:
        return f"{settings.paywall_proxy_prefix}{url}"
    return url


templates.env.filters["to_bogota_local"] = to_bogota_local
templates.env.filters["paywall_url"] = paywall_url
templates.env.globals["paywall_url"] = paywall_url
