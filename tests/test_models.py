import pytest
from sqlalchemy import inspect, select, func
from sqlalchemy.orm import Session
from app.db import Base, make_engine
from app.models import Source, Article

@pytest.fixture
def session(tmp_path):
    db_file = tmp_path / "test.db"
    engine = make_engine(str(db_file))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()

def test_all_tables_present(session):
    engine = session.get_bind()
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    expected = {
        "sources", "articles", "tags", "article_tags", "user_actions",
        "notes", "briefings", "source_fetch_logs", "score_runs",
        "article_uses", "ai_annotations", "article_embeddings", "story_clusters"
    }
    assert expected.issubset(tables)

def test_insert_relationship(session):
    source = Source(
        slug="test-source",
        name="Test Source",
        url="https://example.com",
        kind="rss",
        source_type="official_blog",
        topic="ai"
    )
    session.add(source)
    session.flush()
    
    article = Article(
        source_id=source.id,
        title="Test Article",
        raw_title="Test Article",
        normalized_title="test article",
        original_url="https://example.com/a1",
        canonical_url="https://example.com/a1",
        dedup_hash="hash1",
        content_hash="chash1",
        language="en",
        country_scope="global",
        topic="ai",
        urgency="normal",
        reading_time_minutes=1,
        scraping_method="rss"
    )
    session.add(article)
    session.commit()
    
    # Refresh to check relationship
    session.refresh(source)
    assert len(source.articles) == 1
    assert source.articles[0].title == "Test Article"

def test_cascade_delete(session):
    source = Source(
        slug="test-source",
        name="Test Source",
        url="https://example.com",
        kind="rss",
        source_type="official_blog",
        topic="ai"
    )
    session.add(source)
    session.flush()
    
    article = Article(
        source_id=source.id,
        title="Test Article",
        raw_title="Test Article",
        normalized_title="test article",
        original_url="https://example.com/a1",
        canonical_url="https://example.com/a1",
        dedup_hash="hash1",
        content_hash="chash1",
        language="en",
        country_scope="global",
        topic="ai",
        urgency="normal",
        reading_time_minutes=1,
        scraping_method="rss"
    )
    session.add(article)
    session.commit()
    
    # Ensure article exists
    assert session.scalar(select(func.count()).select_from(Article)) == 1
    
    # Delete source
    session.delete(source)
    session.commit()
    
    # Article should be gone due to ON DELETE CASCADE
    assert session.scalar(select(func.count()).select_from(Article)) == 0
