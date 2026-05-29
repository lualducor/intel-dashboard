import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db import get_db
from app.models import Source, Article, ScoreRun
from app.routers.score_debug import router as score_debug_router

# Manually include the router for testing since it's not in app/main.py
# and we are forbidden from modifying app/main.py.
if not any(route.path.startswith("/debug/scoring") for route in app.routes):
    app.include_router(score_debug_router)

def test_score_debug_flow(db_factory):
    # Setup DB override
    def _get_db_override():
        session = db_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_db_override
    client = TestClient(app)

    # Insert fixtures
    db = db_factory()
    source = Source(
        slug="test-source",
        name="Test Source",
        url="http://example.com",
        kind="rss",
        source_type="news",
        topic="ai",
        trust_score=0.8,
        source_priority=0.7
    )
    db.add(source)
    db.commit()

    article = Article(
        source_id=source.id,
        title="The agentic future of AI",
        raw_title="The agentic future of AI",
        normalized_title="the agentic future of ai",
        original_url="http://example.com/a1",
        canonical_url="http://example.com/a1",
        dedup_hash="hash1",
        content_hash="chash1",
        language="en",
        country_scope="global",
        topic="ai",
        urgency="low",
        reading_time_minutes=5,
        scraping_method="rss",
        final_score=0.0
    )
    db.add(article)
    db.commit()

    run = ScoreRun(
        article_id=article.id,
        score_version="v1_base",
        final_score=0.0,
        explanation="initial",
        source_score=0.0,
        freshness_score=0.0,
        keyword_score=0.0,
        category_score=0.0,
        user_feedback_score=0.0,
        novelty_score=0.0
    )
    db.add(run)
    db.commit()

    article_id = article.id
    db.close()

    try:
        # GET /debug/scoring/{id} -> 200
        resp = client.get(f"/debug/scoring/{article_id}")
        assert resp.status_code == 200
        assert "The agentic future of AI" in resp.text
        assert "Recalculate" in resp.text

        # GET /debug/scoring/999999 -> 404
        resp = client.get("/debug/scoring/999999")
        assert resp.status_code == 404

        # POST /debug/scoring/{id}/recalc -> 303
        resp = client.post(f"/debug/scoring/{article_id}/recalc", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == f"/debug/scoring/{article_id}"

        # Verify results in DB
        db2 = db_factory()
        article_after = db2.get(Article, article_id)
        assert article_after.final_score > 0.0
        
        runs = db2.scalars(
            select(ScoreRun).where(ScoreRun.article_id == article_id)
        ).all()
        assert len(runs) == 2
        db2.close()

    finally:
        app.dependency_overrides.clear()
