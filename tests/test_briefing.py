import json
from datetime import datetime, timezone

from app.config import get_settings
from app.models import Article, Briefing, Source
from app.services import briefing


def test_generate_briefing_creates_ordered_must_read_briefing(db_factory):
    db = db_factory()
    now = datetime.now(timezone.utc)
    source = Source(
        slug="briefing-source",
        name="Briefing Source",
        url="https://example.com",
        feed_url="https://example.com/feed.xml",
        kind="rss",
        source_type="news",
        topic="ai",
    )
    db.add(source)
    db.flush()

    def article(title: str, score: float, suffix: str) -> Article:
        return Article(
            source_id=source.id,
            title=title,
            raw_title=title,
            normalized_title=title.lower(),
            original_url=f"https://example.com/{suffix}",
            canonical_url=f"https://example.com/{suffix}",
            dedup_hash=f"briefing-hash-{suffix}",
            content_hash=f"briefing-content-{suffix}",
            language="en",
            country_scope="global",
            topic="ai",
            urgency="normal",
            reading_time_minutes=4,
            fetched_at=now,
            scraping_method="rss",
            status="new",
            final_score=score,
            score_explanation=f"score explanation {suffix}",
        )

    high = article("Highest Scoring AI Story", 0.85, "high")
    qualifying = article("Second Qualifying AI Story", 0.75, "second")
    low = article("Low Scoring AI Story", 0.2, "low")
    db.add_all([high, qualifying, low])
    db.commit()

    generated = briefing.generate_briefing(db, get_settings())

    assert db.get(Briefing, generated.id) is not None
    assert "Highest Scoring AI Story" in generated.body_markdown
    assert json.loads(generated.article_ids_json) == [high.id, qualifying.id]
    assert briefing.get_latest_briefing(db).id == generated.id
    assert briefing.article_groups(db, generated)["ai"] == [high, qualifying]


def test_article_groups_handles_missing_or_invalid_briefing_data(db_factory):
    db = db_factory()

    assert briefing.article_groups(db, None) == {"ai": [], "colombia": [], "crypto": []}

    invalid = Briefing(
        body_markdown="invalid",
        article_ids_json="not-json",
        score_version="test",
    )
    db.add(invalid)
    db.commit()

    assert briefing.article_groups(db, invalid) == {
        "ai": [],
        "colombia": [],
        "crypto": [],
    }
