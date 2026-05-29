import json

from app.models import Article, ArticleUse, Source
from app.services.exporter import export_as


def _seed(db):
    source = Source(
        slug="export-source",
        name="Export Source",
        url="https://example.com",
        kind="rss",
        source_type="news",
        topic="ai",
    )
    db.add(source)
    db.flush()

    saved = Article(
        source_id=source.id,
        title="Saved Export Article",
        raw_title="Saved Export Article",
        normalized_title="saved export article",
        original_url="https://example.com/saved",
        canonical_url="https://example.com/saved",
        dedup_hash="export-saved-hash",
        content_hash="export-saved-content",
        language="en",
        country_scope="global",
        topic="ai",
        category="models",
        urgency="normal",
        reading_time_minutes=3,
        scraping_method="rss",
        status="saved",
        final_score=0.87654,
    )
    used = Article(
        source_id=source.id,
        title="Content Use Article",
        raw_title="Content Use Article",
        normalized_title="content use article",
        original_url="https://example.com/content",
        canonical_url="https://example.com/content",
        dedup_hash="export-content-hash",
        content_hash="export-content-content",
        language="en",
        country_scope="global",
        topic="ai",
        category="tools",
        urgency="normal",
        reading_time_minutes=4,
        scraping_method="rss",
        status="new",
        final_score=0.65432,
    )
    db.add_all([saved, used])
    db.flush()
    db.add(
        ArticleUse(
            article_id=used.id,
            status="idea",
            use_type="linkedin",
            content_angle="Explain the workflow",
        )
    )
    db.commit()
    return saved, used


def test_exporter_formats(db_factory):
    db = db_factory()
    try:
        saved, used = _seed(db)

        markdown = export_as(db, "md", status_in=["saved"])
        assert saved.title in markdown
        assert markdown.splitlines()[0].startswith("- ")

        parsed = json.loads(export_as(db, "json", status_in=["saved"]))
        assert isinstance(parsed, list)
        assert "final_score" in parsed[0]

        csv_body = export_as(db, "csv", status_in=["saved"])
        assert "title" in csv_body.splitlines()[0]

        content_markdown = export_as(db, "md", for_content=True)
        assert used.title in content_markdown
    finally:
        db.close()
