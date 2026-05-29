import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db
from app.models import Article, Source, ArticleUse
from app.services import queues

def test_saved_articles_logic(db_factory):
    db = db_factory()
    source = Source(slug="test", name="Test", url="http://test.com", kind="rss", source_type="blog", topic="ai")
    db.add(source)
    db.flush()

    # (A) status='saved' WITH an ArticleUse(status='idea')
    a_saved_idea = Article(
        source_id=source.id, title="Saved Idea", raw_title="Saved Idea", 
        normalized_title="Saved Idea", original_url="http://a.com", canonical_url="http://a.com",
        dedup_hash="ha", content_hash="ca", language="en", country_scope="global", topic="ai",
        urgency="normal", reading_time_minutes=5, scraping_method="rss", status="saved", final_score=0.9
    )
    # (B) status='saved' with NO use
    a_saved_no_use = Article(
        source_id=source.id, title="Saved No Use", raw_title="Saved No Use", 
        normalized_title="Saved No Use", original_url="http://b.com", canonical_url="http://b.com",
        dedup_hash="hb", content_hash="cb", language="en", country_scope="global", topic="ai",
        urgency="normal", reading_time_minutes=5, scraping_method="rss", status="saved", final_score=0.8
    )
    # (C) status='archived'
    a_archived = Article(
        source_id=source.id, title="Archived", raw_title="Archived", 
        normalized_title="Archived", original_url="http://c.com", canonical_url="http://c.com",
        dedup_hash="hc", content_hash="cc", language="en", country_scope="global", topic="ai",
        urgency="normal", reading_time_minutes=5, scraping_method="rss", status="archived", final_score=0.7
    )
    db.add_all([a_saved_idea, a_saved_no_use, a_archived])
    db.flush()

    use = ArticleUse(article_id=a_saved_idea.id, use_type="twitch", status="idea")
    db.add(use)
    db.commit()

    # queues.saved_articles(db) returns A and B (not C).
    saved = queues.saved_articles(db)
    assert len(saved) == 2
    titles = [a.title for a in saved]
    assert "Saved Idea" in titles
    assert "Saved No Use" in titles
    assert "Archived" not in titles

    # queues.saved_articles(db, filter="for_content") returns ONLY A.
    for_content = queues.saved_articles(db, filter="for_content")
    assert len(for_content) == 1
    assert for_content[0].title == "Saved Idea"

    # queues.archived_articles(db) returns only C.
    archived = queues.archived_articles(db)
    assert len(archived) == 1
    assert archived[0].title == "Archived"

def test_saved_route(db_factory):
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
        a_saved_idea = Article(
            source_id=source.id, title="Saved Idea", raw_title="Saved Idea", 
            normalized_title="Saved Idea", original_url="http://a.com", canonical_url="http://a.com",
            dedup_hash="ha", content_hash="ca", language="en", country_scope="global", topic="ai",
            urgency="normal", reading_time_minutes=5, scraping_method="rss", status="saved", final_score=0.9
        )
        a_saved_no_use = Article(
            source_id=source.id, title="Saved No Use", raw_title="Saved No Use", 
            normalized_title="Saved No Use", original_url="http://b.com", canonical_url="http://b.com",
            dedup_hash="hb", content_hash="cb", language="en", country_scope="global", topic="ai",
            urgency="normal", reading_time_minutes=5, scraping_method="rss", status="saved", final_score=0.8
        )
        db.add_all([a_saved_idea, a_saved_no_use])
        db.flush()
        use = ArticleUse(article_id=a_saved_idea.id, use_type="twitch", status="idea")
        db.add(use)
        db.commit()

        resp = client.get("/saved")
        assert resp.status_code == 200
        assert "Saved Idea" in resp.text
        assert "Saved No Use" in resp.text

        resp = client.get("/saved?filter=for_content")
        assert resp.status_code == 200
        assert "Saved Idea" in resp.text
        assert "Saved No Use" not in resp.text
    finally:
        app.dependency_overrides.clear()
