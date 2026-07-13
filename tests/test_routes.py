import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db
from app.models import Article, Source
from app.config import get_settings

@pytest.fixture
def client(db_factory):
    # Get a session from the factory
    session = db_factory()
    
    def override_get_db():
        try:
            yield session
        finally:
            # We don't close it here because we might need it in the test
            # but the fixture will handle it.
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client, session
    app.dependency_overrides.clear()
    session.close()

def test_healthz(client):
    api_client, _ = client
    response = api_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cross_origin_write_is_rejected(client):
    api_client, _ = client
    response = api_client.post(
        "/ingest/run",
        headers={"Origin": "https://malicious.example"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "cross-origin writes are not allowed"

def test_dashboard_empty(client):
    api_client, _ = client
    response = api_client.get("/")
    assert response.status_code == 200
    html = response.text
    # Check for queue tab labels
    assert "Must Read" in html
    assert "Maybe Useful" in html
    assert "For Content" in html
    assert "Noise" in html
    # Check for empty state (assuming templates use something like 'No articles found')
    assert "No articles" in html or "empty" in html.lower()

def test_feed_empty(client):
    api_client, _ = client
    response = api_client.get("/feed?queue=must_read")
    assert response.status_code == 200
    # Should return a partial, check for empty state
    assert "No articles" in response.text or "empty" in response.text.lower()

def test_feed_with_data(client):
    api_client, session = client
    
    # Insert data
    source = Source(
        slug="tech", name="Tech", url="x", kind="rss", 
        source_type="news", topic="ai", active=True
    )
    session.add(source)
    session.commit()
    
    article = Article(
        source_id=source.id,
        title="Breaking AI News",
        raw_title="Breaking AI News",
        normalized_title="breaking ai news",
        original_url="https://x.com/1",
        canonical_url="https://x.com/1",
        dedup_hash="hash1",
        content_hash="chash1",
        language="en",
        country_scope="global",
        topic="ai",
        urgency="high",
        reading_time_minutes=3,
        scraping_method="rss",
        final_score=0.9, # Must Read
        status="new"
    )
    session.add(article)
    session.commit()
    
    # Test feed
    response = api_client.get("/feed?queue=must_read")
    assert response.status_code == 200
    assert "Breaking AI News" in response.text

    # Test dashboard also shows it
    response = api_client.get("/")
    assert response.status_code == 200
    assert "Breaking AI News" in response.text


def test_feed_paginates(client):
    api_client, session = client
    settings = get_settings()
    original_page_size = settings.feed_page_size
    settings.feed_page_size = 1
    try:
        source = Source(
            slug="paged-tech",
            name="Paged Tech",
            url="https://paged.example",
            kind="rss",
            source_type="news",
            topic="ai",
            active=True,
        )
        session.add(source)
        session.flush()
        for index in range(2):
            session.add(
                Article(
                    source_id=source.id,
                    title=f"Paged AI {index}",
                    raw_title=f"Paged AI {index}",
                    normalized_title=f"paged ai {index}",
                    original_url=f"https://paged.example/{index}",
                    canonical_url=f"https://paged.example/{index}",
                    dedup_hash=f"paged-{index}",
                    content_hash=f"paged-content-{index}",
                    language="en",
                    country_scope="global",
                    topic="ai",
                    urgency="normal",
                    reading_time_minutes=1,
                    scraping_method="rss",
                    final_score=0.9 - index * 0.01,
                    status="new",
                )
            )
        session.commit()

        first = api_client.get("/feed?queue=must_read")
        second = api_client.get("/feed?queue=must_read&page=2")

        assert first.status_code == second.status_code == 200
        assert "Paged AI 0" in first.text
        assert "Paged AI 1" not in first.text
        assert "page=2" in first.text
        assert "Paged AI 1" in second.text
    finally:
        settings.feed_page_size = original_page_size
