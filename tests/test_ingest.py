import httpx
import respx
from datetime import datetime, timezone
from sqlalchemy import func, select

from app.models import Article, ScoreRun, Source
from app.services import ingest
from app.services import extractor

FEED_URL = "https://test.local/feed.xml"
SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Test Feed</title>
<item>
  <title>Agentic AI agent breakthrough</title>
  <link>https://test.local/a1?utm_source=rss</link>
  <description>An autonomous multi-agent system for AI workflow.</description>
  <pubDate>Wed, 27 May 2026 12:00:00 GMT</pubDate>
  <author>x@test</author>
</item>
<item>
  <title>LLM tool-use and mcp update</title>
  <link>https://test.local/a2</link>
  <description>function calling and orchestration.</description>
  <pubDate>Wed, 27 May 2026 11:00:00 GMT</pubDate>
</item>
</channel></rss>
"""


def _seed_source(db_factory):
    db = db_factory()
    db.add(
        Source(
            slug="test",
            name="Test",
            url="https://test.local",
            feed_url=FEED_URL,
            kind="rss",
            source_type="official_blog",
            topic="ai",
            trust_score=0.9,
            source_priority=0.8,
            default_language="en",
            default_country_scope="global",
        )
    )
    db.commit()
    db.close()


async def test_run_ingest_inserts_and_is_idempotent(db_factory):
    _seed_source(db_factory)

    with respx.mock:
        respx.get(FEED_URL).mock(return_value=httpx.Response(200, text=SAMPLE))
        res = await ingest.run_ingest(session_factory=db_factory, force=True)

    assert res["locked"] is False
    assert res["totals"]["items_new"] == 2

    db = db_factory()
    count = db.scalar(select(func.count()).select_from(Article))
    runs = db.scalar(select(func.count()).select_from(ScoreRun))
    # canonicalize stripped utm_source; first article scored on agentic terms
    art = db.scalars(select(Article).where(Article.title.like("Agentic%"))).first()
    assert count == 2
    assert runs == 2
    assert art.canonical_url == "https://test.local/a1"
    assert "agentic-ai" in [t.name for t in art.tags]
    assert art.final_score > 0
    assert art.score_explanation
    db.close()

    # second pass over the same feed: dedupe -> zero new
    with respx.mock:
        respx.get(FEED_URL).mock(return_value=httpx.Response(200, text=SAMPLE))
        res2 = await ingest.run_ingest(session_factory=db_factory, force=True)
    assert res2["totals"]["items_new"] == 0

    db = db_factory()
    assert db.scalar(select(func.count()).select_from(Article)) == 2
    db.close()


async def test_run_ingest_failure_marks_source(db_factory):
    _seed_source(db_factory)
    with respx.mock:
        respx.get(FEED_URL).mock(return_value=httpx.Response(503))
        res = await ingest.run_ingest(session_factory=db_factory, force=True)

    src_result = res["sources"][0]
    assert src_result["ok"] is False
    db = db_factory()
    src = db.scalars(select(Source)).first()
    assert src.consecutive_failures == 1
    assert src.last_error_at is not None
    db.close()


async def test_ingest_applies_source_age_and_item_limits(db_factory):
    db = db_factory()
    db.add(
        Source(
            slug="limited",
            name="Limited",
            url="https://limited.local",
            feed_url="https://limited.local/feed.xml",
            kind="rss",
            source_type="official_blog",
            topic="ai",
            max_items_per_fetch=1,
            max_item_age_days=7,
        )
    )
    db.commit()
    db.close()
    feed = """<?xml version="1.0"?><rss version="2.0"><channel><title>Limited</title>
    <item><title>Recent one</title><link>https://limited.local/1</link><pubDate>Wed, 27 May 2026 12:00:00 GMT</pubDate></item>
    <item><title>Recent two</title><link>https://limited.local/2</link><pubDate>Tue, 26 May 2026 12:00:00 GMT</pubDate></item>
    <item><title>Historical</title><link>https://limited.local/old</link><pubDate>Fri, 01 May 2026 12:00:00 GMT</pubDate></item>
    </channel></rss>"""

    with respx.mock:
        respx.get("https://limited.local/feed.xml").mock(
            return_value=httpx.Response(
                200,
                text=feed,
                headers={"ETag": '"limited-v1"', "Last-Modified": "Wed, 27 May 2026 13:00:00 GMT"},
            )
        )
        result = await ingest.run_ingest(
            session_factory=db_factory,
            force=True,
            now=datetime(2026, 5, 28, tzinfo=timezone.utc),
        )

    source_result = result["sources"][0]
    assert source_result["items_seen"] == 3
    assert source_result["items_skipped_old"] == 1
    assert source_result["items_skipped_limit"] == 1
    assert source_result["items_new"] == 1

    db = db_factory()
    source = db.scalar(select(Source).where(Source.slug == "limited"))
    assert source.feed_etag == '"limited-v1"'
    assert source.feed_last_modified == "Wed, 27 May 2026 13:00:00 GMT"
    assert db.scalar(select(func.count()).select_from(Article)) == 1
    db.close()


async def test_ingest_not_modified_is_a_successful_noop(db_factory):
    _seed_source(db_factory)
    db = db_factory()
    source = db.scalar(select(Source).where(Source.slug == "test"))
    source.feed_etag = '"test-v1"'
    db.commit()
    db.close()

    def responder(request):
        assert request.headers["if-none-match"] == '"test-v1"'
        return httpx.Response(304)

    with respx.mock:
        respx.get(FEED_URL).mock(side_effect=responder)
        result = await ingest.run_ingest(session_factory=db_factory, force=True)

    assert result["sources"][0]["ok"] is True
    assert result["sources"][0]["not_modified"] is True
    assert result["totals"]["items_new"] == 0


async def test_ingest_enriches_a_limited_number_of_missing_summaries(
    db_factory, monkeypatch
):
    _seed_source(db_factory)
    feed = """<?xml version="1.0"?><rss version="2.0"><channel><title>Missing</title>
    <item><title>Agent system without summary</title><link>https://test.local/missing</link><pubDate>Sun, 12 Jul 2026 12:00:00 GMT</pubDate></item>
    </channel></rss>"""

    def fake_extract(url, **kwargs):
        return extractor.Extracted(
            title="",
            summary="An autonomous agent orchestration system.",
            text=None,
            author="Reporter",
            published_at=None,
            language="en",
        )

    monkeypatch.setattr(extractor, "extract", fake_extract)
    with respx.mock:
        respx.get(FEED_URL).mock(return_value=httpx.Response(200, text=feed))
        result = await ingest.run_ingest(session_factory=db_factory, force=True)

    assert result["totals"]["items_new"] == 1
    db = db_factory()
    article = db.scalar(select(Article))
    assert article.summary == "An autonomous agent orchestration system."
    assert article.author == "Reporter"
    assert article.enriched_at is not None
    db.close()


async def test_enrichment_failure_does_not_fail_source(db_factory, monkeypatch):
    _seed_source(db_factory)
    feed = """<?xml version="1.0"?><rss version="2.0"><channel><title>Missing</title>
    <item><title>Story without summary</title><link>https://test.local/unavailable</link><pubDate>Sun, 12 Jul 2026 12:00:00 GMT</pubDate></item>
    </channel></rss>"""

    def failed_extract(url, **kwargs):
        raise httpx.TimeoutException("article page timed out")

    monkeypatch.setattr(extractor, "extract", failed_extract)
    with respx.mock:
        respx.get(FEED_URL).mock(return_value=httpx.Response(200, text=feed))
        result = await ingest.run_ingest(session_factory=db_factory, force=True)

    assert result["sources"][0]["ok"] is True
    assert result["totals"]["items_new"] == 1
    db = db_factory()
    article = db.scalar(select(Article))
    assert article.summary is None
    db.close()
