from datetime import datetime, timezone, timedelta
import re
import unicodedata


COLOMBIA_KEYWORDS = [
    "bogota",
    "medellin",
    "colombia",
    "cali",
    "barranquilla",
    "cartagena",
    "cucuta",
    "bucaramanga",
]


def _strip_accents_lower(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(
        c for c in decomposed if unicodedata.category(c) != "Mn"
    ).lower()


def country_scope(default_country_scope: str, title: str, summary: str | None) -> str:
    if default_country_scope == "co":
        return "co"

    text = _strip_accents_lower((title or "") + " " + (summary or ""))
    if default_country_scope == "global" and any(keyword in text for keyword in COLOMBIA_KEYWORDS):
        return "co"
    return default_country_scope


def language(default_language: str, entry_language: str | None) -> str:
    if isinstance(entry_language, str) and entry_language:
        return entry_language[:2].lower()
    return default_language


def urgency(
    title: str,
    source_type: str,
    published_at: datetime | None,
    *,
    now: datetime | None = None,
) -> str:
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if re.search(r"breaking|urgent|just in", title or "", re.IGNORECASE):
        return "breaking"

    if published_at is None:
        return "normal"

    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    age = now - published_at
    if age <= timedelta(hours=2) and source_type in {"tech_media", "local_news"}:
        return "breaking"
    if age > timedelta(days=30):
        return "evergreen"
    return "normal"


def reading_time_minutes(summary: str | None) -> int:
    words = len((summary or "").split())
    return max(1, round(words / 200))
