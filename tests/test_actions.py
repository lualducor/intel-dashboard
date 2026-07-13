import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_db
from app.main import app
from datetime import datetime, timedelta, timezone

from app.models import Article, ArticleUse, Source, UserAction
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
    with TestClient(app) as test_client:
        yield test_client, session
    app.dependency_overrides.clear()
    session.close()


def insert_article(session):
    source = Source(
        slug="action-source",
        name="Action Source",
        url="https://example.com",
        kind="rss",
        source_type="news",
        topic="ai",
    )
    session.add(source)
    session.flush()

    article = Article(
        source_id=source.id,
        title="Action Article",
        raw_title="Action Article",
        normalized_title="action article",
        original_url="https://example.com/action",
        canonical_url="https://example.com/action",
        dedup_hash="action-hash",
        content_hash="action-content-hash",
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


def test_useful_sets_saved_and_records_action(client):
    api_client, session = client
    article = insert_article(session)

    response = api_client.post(f"/articles/{article.id}/useful")

    assert response.status_code == 200
    assert json.loads(response.headers["HX-Trigger-After-Swap"])[
        "articleActionCompleted"
    ] == {"articleId": article.id, "action": "useful"}
    session.refresh(article)
    assert article.status == "saved"
    action = session.scalar(
        select(UserAction).where(
            UserAction.article_id == article.id,
            UserAction.action == "useful",
        )
    )
    assert action is not None


def test_not_relevant_sets_ignored(client):
    api_client, session = client
    article = insert_article(session)

    response = api_client.post(f"/articles/{article.id}/not_relevant")

    assert response.status_code == 200
    session.refresh(article)
    assert article.status == "ignored"


def test_used_for_content_creates_article_use(client):
    api_client, session = client
    article = insert_article(session)

    response = api_client.post(
        f"/articles/{article.id}/used_for_content",
        data={"use_type": "linkedin"},
    )

    assert response.status_code == 200
    article_use = session.scalar(
        select(ArticleUse).where(ArticleUse.article_id == article.id)
    )
    assert article_use is not None
    assert article_use.status == "idea"
    assert article_use.use_type == "linkedin"


def test_for_content_quick_action_creates_default_use(client):
    api_client, session = client
    article = insert_article(session)

    response = api_client.post(f"/articles/{article.id}/for_content")

    assert response.status_code == 200
    session.refresh(article)
    assert article.status == "used"
    article_use = session.scalar(
        select(ArticleUse).where(ArticleUse.article_id == article.id)
    )
    assert article_use is not None
    assert article_use.use_type == "personal_reading"


def test_bulk_archive_only_old_ai_inbox_items(client):
    api_client, session = client
    old_ai = insert_article(session)
    old_ai.fetched_at = datetime.now(timezone.utc) - timedelta(days=31)

    source = old_ai.source
    colombia = Article(
        source_id=source.id,
        title="Old Colombia",
        raw_title="Old Colombia",
        normalized_title="old colombia",
        original_url="https://example.com/old-colombia",
        canonical_url="https://example.com/old-colombia",
        dedup_hash="old-colombia-hash",
        content_hash="old-colombia-content",
        language="es",
        country_scope="co",
        topic="colombia",
        urgency="normal",
        reading_time_minutes=2,
        scraping_method="rss",
        status="new",
        fetched_at=datetime.now(timezone.utc) - timedelta(days=31),
    )
    session.add(colombia)
    session.commit()

    response = api_client.post("/bulk/articles/archive-old", data={"days": 30})

    assert response.status_code == 200
    assert response.json()["archived"] == 1
    session.refresh(old_ai)
    session.refresh(colombia)
    assert old_ai.status == "archived"
    assert colombia.status == "new"


def test_bulk_archive_uses_publication_date_and_can_target_source(client):
    api_client, session = client
    article = insert_article(session)
    article.published_at = datetime.now(timezone.utc) - timedelta(days=8)
    article.fetched_at = datetime.now(timezone.utc)
    session.commit()

    response = api_client.post(
        "/bulk/articles/archive-old",
        data={"days": 7, "source": "action-source"},
    )

    assert response.status_code == 200
    assert response.json()["archived"] == 1
    assert response.json()["source"] == "action-source"
    session.refresh(article)
    assert article.status == "archived"


def test_unknown_action_and_missing_article_return_errors(client):
    api_client, session = client
    article = insert_article(session)

    response = api_client.post(f"/articles/{article.id}/bogus")
    assert response.status_code == 400

    response = api_client.post("/articles/999999/save")
    assert response.status_code == 404
