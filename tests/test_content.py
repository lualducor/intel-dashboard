import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.db import get_db
from app.models import Article, ArticleUse, Source
from app.routers.content import router as content_router

# Inject the router since we aren't allowed to modify app/main.py
# This ensures the TestClient can find the new endpoints.
app.include_router(content_router)

@pytest.fixture
def client(db_factory):
    # Setup dependency override
    session_factory = db_factory
    
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

def test_article_use_upsert_and_content_page(client, db_factory):
    session_factory = db_factory
    
    # 1. Seed Source and Article
    with session_factory() as db:
        source = Source(
            slug="tech-crunch",
            name="TechCrunch",
            url="https://techcrunch.com",
            kind="rss",
            source_type="blog",
            topic="ai",
            active=True,
        )
        db.add(source)
        db.flush()

        article = Article(
            source_id=source.id,
            title="AI is evolving fast",
            raw_title="AI is evolving fast",
            normalized_title="ai is evolving fast",
            original_url="https://techcrunch.com/ai-evolving",
            canonical_url="https://techcrunch.com/ai-evolving",
            dedup_hash="unique-hash-123",
            content_hash="content-hash-123",
            language="en",
            country_scope="global",
            topic="ai",
            urgency="normal",
            reading_time_minutes=3,
            scraping_method="rss",
            status="saved"
        )
        db.add(article)
        db.commit()
        article_id = article.id

    # 2. POST /content/use/{id} with {"use_type":"linkedin","status":"idea"}
    response = client.post(
        f"/content/use/{article_id}",
        data={"use_type": "linkedin", "status": "idea"}
    )
    assert response.status_code == 200
    assert "linkedin: idea" in response.text

    # Verify ArticleUse row exists
    with session_factory() as db:
        stmt = select(ArticleUse).where(
            ArticleUse.article_id == article_id, 
            ArticleUse.use_type == "linkedin"
        )
        use = db.execute(stmt).scalar_one()
        assert use.status == "idea"

    # 3. POST /content/use/{id} again with {"use_type":"linkedin","status":"drafted"}
    response = client.post(
        f"/content/use/{article_id}",
        data={"use_type": "linkedin", "status": "drafted"}
    )
    assert response.status_code == 200
    assert "linkedin: drafted" in response.text

    # Verify the SAME row is updated
    with session_factory() as db:
        stmt = select(ArticleUse).where(ArticleUse.article_id == article_id)
        uses = db.execute(stmt).scalars().all()
        assert len(uses) == 1
        assert uses[0].status == "drafted"
        assert uses[0].use_type == "linkedin"

    # 4. GET /content
    response = client.get("/content")
    assert response.status_code == 200
    assert "AI is evolving fast" in response.text
    assert "linkedin" in response.text
    assert "drafted" in response.text
