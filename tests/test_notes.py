import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_db
from app.main import app
from app.models import Article, Note, Source
from app.routers import actions, notes


def include_test_routers():
    paths = {route.path for route in app.router.routes if hasattr(route, "path")}
    if "/articles/{article_id}/notes" not in paths:
        app.include_router(notes.router)
    if "/articles/{article_id}/{action}" not in paths:
        app.include_router(actions.router)


@pytest.fixture
def client(db_factory):
    session = db_factory()

    include_test_routers()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app), session
    app.dependency_overrides.clear()
    session.close()


def insert_article(session):
    source = Source(
        slug="note-source",
        name="Note Source",
        url="https://example.com",
        kind="rss",
        source_type="news",
        topic="ai",
    )
    session.add(source)
    session.flush()

    article = Article(
        source_id=source.id,
        title="Note Article",
        raw_title="Note Article",
        normalized_title="note article",
        original_url="https://example.com/note",
        canonical_url="https://example.com/note",
        dedup_hash="note-hash",
        content_hash="note-content-hash",
        language="en",
        country_scope="global",
        topic="ai",
        urgency="normal",
        reading_time_minutes=3,
        scraping_method="rss",
        status="new",
    )
    session.add(article)
    session.commit()
    return article


def test_add_note(client):
    api_client, session = client
    article = insert_article(session)

    response = api_client.post(
        f"/articles/{article.id}/notes",
        data={"body": "my note"},
    )

    assert response.status_code == 200
    note = session.scalar(select(Note).where(Note.article_id == article.id))
    assert note is not None
    assert note.body == "my note"
