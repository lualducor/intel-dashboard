from datetime import datetime, timezone, timedelta

from app.services.derive import (
    country_scope,
    language,
    reading_time_minutes,
    urgency,
)


def test_country_scope_escalates_global_to_co_on_colombia_keyword_in_title():
    assert country_scope("global", "Bogotá launches metro update", None) == "co"


def test_country_scope_never_demotes_co():
    assert country_scope("co", "Global markets rally", "No local keyword") == "co"


def test_country_scope_stays_global_without_colombia_keyword():
    assert country_scope("global", "Global markets rally", "Tech stocks rise") == "global"


def test_language_uses_entry_override_else_default():
    assert language("es", "en-US") == "en"
    assert language("es", None) == "es"
    assert language("es", "") == "es"


def test_urgency_title_breaking_is_breaking():
    now = datetime(2026, 5, 28, 12, 0, tzinfo=timezone.utc)

    assert urgency("BREAKING: major update", "blog", None, now=now) == "breaking"


def test_urgency_fresh_tech_media_is_breaking():
    now = datetime(2026, 5, 28, 12, 0, tzinfo=timezone.utc)
    published_at = now - timedelta(hours=1)

    assert urgency("Major update", "tech_media", published_at, now=now) == "breaking"


def test_urgency_old_article_is_evergreen():
    now = datetime(2026, 5, 28, 12, 0, tzinfo=timezone.utc)
    published_at = now - timedelta(days=40)

    assert urgency("Analysis", "tech_media", published_at, now=now) == "evergreen"


def test_urgency_normal_otherwise():
    now = datetime(2026, 5, 28, 12, 0, tzinfo=timezone.utc)
    published_at = now - timedelta(days=1)

    assert urgency("Analysis", "blog", published_at, now=now) == "normal"


def test_urgency_none_published_at_is_normal():
    now = datetime(2026, 5, 28, 12, 0, tzinfo=timezone.utc)

    assert urgency("Analysis", "tech_media", None, now=now) == "normal"


def test_reading_time_minutes_empty_and_400_words():
    assert reading_time_minutes("") == 1
    assert reading_time_minutes("word " * 400) == 2
