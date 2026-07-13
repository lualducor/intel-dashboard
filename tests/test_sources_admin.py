from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_db
from app.main import app
from app.models import Source
from app.routers.sources_admin import router as sources_admin_router


def _include_router():
    if not any(route.path == "/sources" for route in app.routes):
        app.include_router(sources_admin_router)


def _seed(db):
    source = Source(
        slug="admin-source",
        name="Admin Source",
        url="https://example.com",
        kind="rss",
        source_type="news",
        topic="ai",
        active=True,
        trust_score=0.5,
        source_priority=0.5,
    )
    db.add(source)
    db.commit()
    return source


def test_sources_admin_routes(db_factory):
    _include_router()
    db = db_factory()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        source = _seed(db)
        client = TestClient(app)

        response = client.post(f"/sources/{source.slug}/toggle")
        assert response.status_code == 200
        db.refresh(source)
        assert source.active is False

        response = client.post(
            f"/sources/{source.slug}/edit",
            data={
                "feed_url": "https://example.com/feed.xml",
                "trust_score": "0.9",
                "source_priority": "0.7",
                "fetch_interval_minutes": "120",
                "max_items_per_fetch": "25",
                "max_item_age_days": "14",
            },
        )
        assert response.status_code == 200
        refreshed = db.scalar(select(Source).where(Source.slug == source.slug))
        assert refreshed.trust_score == 0.9
        assert refreshed.feed_url == "https://example.com/feed.xml"
        assert refreshed.fetch_interval_minutes == 120
        assert refreshed.max_items_per_fetch == 25
        assert refreshed.max_item_age_days == 14

        refreshed.consecutive_failures = 5
        refreshed.active = False
        db.commit()
        response = client.post(f"/sources/{source.slug}/reset")
        assert response.status_code == 200
        db.refresh(refreshed)
        assert refreshed.consecutive_failures == 0
        assert refreshed.active is True

        response = client.get("/sources")
        assert response.status_code == 200
        assert source.name in response.text
    finally:
        app.dependency_overrides.clear()
        db.close()
