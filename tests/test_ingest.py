import httpx
import respx
from sqlalchemy import func, select

from app.models import Article, ScoreRun, Source
from app.services import ingest

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
