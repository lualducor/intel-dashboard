from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Source
from app.routers.source_health import router as source_health_router
from app.services.source_health import derive_status


def _source(**kwargs) -> Source:
    data = {
        "slug": "test",
        "name": "Test Source",
        "url": "https://example.com",
        "kind": "rss",
        "source_type": "news",
        "topic": "ai",
        "active": True,
        "fetch_interval_minutes": 60,
        "consecutive_failures": 0,
    }
    data.update(kwargs)
    return Source(**data)


def test_derive_status_states():
    now = datetime(2026, 5, 29, tzinfo=timezone.utc)

    assert derive_status(_source(active=False), now=now) == "inactive"
    assert derive_status(_source(consecutive_failures=5), now=now) == "needs_review"
    assert derive_status(_source(consecutive_failures=3), now=now) == "broken"
    assert derive_status(_source(consecutive_failures=1), now=now) == "degraded"
    assert derive_status(_source(last_success_at=now), now=now) == "healthy"
    assert (
        derive_status(
            _source(last_success_at=now - timedelta(days=10), fetch_interval_minutes=60),
            now=now,
        )
        == "stale"
    )


def test_source_health_route(db_factory):
    if not any(route.path == "/sources/health" for route in app.routes):
        app.include_router(source_health_router)

    session = db_factory()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        session.add(_source(slug="health-test", name="Health Test"))
        session.commit()

        response = TestClient(app).get("/sources/health")

        assert response.status_code == 200
        assert "Health Test" in response.text
    finally:
        app.dependency_overrides.clear()
        session.close()
