import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.db import get_db
from app.models import Article, Source
from app.services.search import search_articles
from scripts.rebuild_fts import rebuild

def test_search_articles_logic(db_factory):
    db = db_factory()
    source = Source(slug="test", name="Test", url="http://test.com", kind="rss", source_type="blog", topic="ai")
    db.add(source)
    db.flush()

    a1 = Article(
        source_id=source.id, title="agentic workflows", raw_title="agentic workflows", 
        normalized_title="agentic workflows", original_url="http://a1.com", canonical_url="http://a1.com",
        dedup_hash="h1", content_hash="c1", language="en", country_scope="global", topic="ai",
        urgency="normal", reading_time_minutes=5, scraping_method="rss", final_score=0.9
    )
    a2 = Article(
        source_id=source.id, title="machine learning", raw_title="machine learning", 
        normalized_title="machine learning", original_url="http://a2.com", canonical_url="http://a2.com",
        dedup_hash="h2", content_hash="c2", language="en", country_scope="global", topic="ai",
        urgency="normal", reading_time_minutes=5, scraping_method="rss", final_score=0.8
    )
    db.add_all([a1, a2])
    db.commit()

    # Search logic
    assert len(search_articles(db, "agentic")) == 1
    assert search_articles(db, "agentic")[0].title == "agentic workflows"
    assert search_articles(db, "   ") == []

def test_search_route(db_factory):
    engine = db_factory.kw['bind']
    def override_get_db():
        db = db_factory()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        db = db_factory()
        source = Source(slug="test", name="Test", url="http://test.com", kind="rss", source_type="blog", topic="ai")
        db.add(source)
        db.flush()
        a1 = Article(
            source_id=source.id, title="agentic workflows", raw_title="agentic workflows", 
            normalized_title="agentic workflows", original_url="http://a1.com", canonical_url="http://a1.com",
            dedup_hash="h1", content_hash="c1", language="en", country_scope="global", topic="ai",
            urgency="normal", reading_time_minutes=5, scraping_method="rss", final_score=0.9
        )
        db.add(a1)
        db.commit()

        resp = client.get("/search?q=agentic")
        assert resp.status_code == 200
        assert "agentic workflows" in resp.text

        resp = client.get("/search")
        assert resp.status_code == 200
        assert "Type a query to search" in resp.text
    finally:
        app.dependency_overrides.clear()

def test_rebuild_recovery(db_factory):
    db = db_factory()
    source = Source(slug="test", name="Test", url="http://test.com", kind="rss", source_type="blog", topic="ai")
    db.add(source)
    db.flush()
    a1 = Article(
        source_id=source.id, title="agentic workflows", raw_title="agentic workflows", 
        normalized_title="agentic workflows", original_url="http://a1.com", canonical_url="http://a1.com",
        dedup_hash="h1", content_hash="c1", language="en", country_scope="global", topic="ai",
        urgency="normal", reading_time_minutes=5, scraping_method="rss", final_score=0.9
    )
    db.add(a1)
    db.commit()

    assert len(search_articles(db, "agentic")) == 1

    # Corrupt FTS
    db.execute(text("DELETE FROM articles_fts"))
    db.commit()
    assert len(search_articles(db, "agentic")) == 0

    # Rebuild
    rebuild(session_factory=db_factory)

    # Fresh session
    db2 = db_factory()
    assert len(search_articles(db2, "agentic")) == 1
