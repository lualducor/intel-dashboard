from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from app.models import Article, Source
from scripts.prune import prune

def test_prune_logic(db_factory):
    now = datetime.now(timezone.utc)
    db = db_factory()
    
    # Insert a Source
    source = Source(
        slug="test-source",
        name="Test Source",
        url="https://example.com",
        kind="rss",
        source_type="news",
        topic="ai"
    )
    db.add(source)
    db.commit()
    
    # Insert 3 Articles
    # A: status='ignored', fetched_at = now - 200 days (should be pruned)
    a = Article(
        source_id=source.id,
        title="Article A",
        raw_title="Article A",
        normalized_title="article a",
        original_url="https://example.com/a",
        canonical_url="https://example.com/a",
        dedup_hash="hash-a",
        content_hash="content-a",
        language="en",
        country_scope="global",
        topic="ai",
        urgency="normal",
        reading_time_minutes=5,
        scraping_method="rss",
        status="ignored",
        fetched_at=now - timedelta(days=200)
    )
    # B: status='ignored', fetched_at = now (recent; should NOT be pruned)
    b = Article(
        source_id=source.id,
        title="Article B",
        raw_title="Article B",
        normalized_title="article b",
        original_url="https://example.com/b",
        canonical_url="https://example.com/b",
        dedup_hash="hash-b",
        content_hash="content-b",
        language="en",
        country_scope="global",
        topic="ai",
        urgency="normal",
        reading_time_minutes=5,
        scraping_method="rss",
        status="ignored",
        fetched_at=now
    )
    # C: status='saved', fetched_at = now - 200 days (wrong status; should NOT be pruned)
    c = Article(
        source_id=source.id,
        title="Article C",
        raw_title="Article C",
        normalized_title="article c",
        original_url="https://example.com/c",
        canonical_url="https://example.com/c",
        dedup_hash="hash-c",
        content_hash="content-c",
        language="en",
        country_scope="global",
        topic="ai",
        urgency="normal",
        reading_time_minutes=5,
        scraping_method="rss",
        status="saved",
        fetched_at=now - timedelta(days=200)
    )
    
    db.add_all([a, b, c])
    db.commit()
    
    a_id, b_id, c_id = a.id, b.id, c.id
    db.close()
    
    # Call prune
    count = prune(session_factory=db_factory, now=now)
    assert count == 1
    
    # Verify
    db = db_factory()
    # A is gone
    assert db.get(Article, a_id) is None
    # B and C remain
    assert db.get(Article, b_id) is not None
    assert db.get(Article, c_id) is not None
    db.close()
