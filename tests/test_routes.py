import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db
from app.models import Article, Source

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
    yield TestClient(app), session
    app.dependency_overrides.clear()
    session.close()

def test_healthz(client):
    api_client, _ = client
    response = api_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

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
