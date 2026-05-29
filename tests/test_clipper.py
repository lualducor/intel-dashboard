from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models import Article, ArticleUse, Source
from app.services import clipper, extractor


def test_manual_clip_lifecycle(db_factory, monkeypatch):
    """Verify manual clipping, deduping, and ArticleUse creation."""

    # Monkeypatch the extractor so NO network happens
    def mock_extract(url, **kw):
        return extractor.Extracted(
            title="Agentic AI breakthrough in LLM orchestration",
            summary="autonomous multi-agent system",
            text="long body ...",
            author="X",
            published_at=None,
            language="en",
        )

    monkeypatch.setattr(extractor, "extract", mock_extract)

    # Use a session from the factory
    db = db_factory()

    # 1. First clip
    url = "https://example.com/post"
    art = clipper.clip_url(db, url)

    assert art.scraping_method == "manual"
    assert art.status == "saved"
    assert art.id is not None

    tag_names = [t.name for t in art.tags]
    # The title contains "Agentic AI", which the tagger (via interests.yaml)
    # is expected to map to "agentic-ai".
    assert "agentic-ai" in tag_names
    assert art.final_score > 0

    # 2. Assert a Source with slug "manual-clip" now exists
    source = db.scalar(select(Source).where(Source.slug == "manual-clip"))
    assert source is not None

    # 3. Dedupe: clipping the SAME url again returns the SAME article
    art2 = clipper.clip_url(db, url)
    assert art2.id == art.id

    count = db.scalar(
        select(func.count(Article.id)).where(Article.original_url == url)
    )
    assert count == 1

    # 4. Use type: clipper.clip_url(db, ..., use_type="blog")
    url2 = "https://example.com/post2"
    art3 = clipper.clip_url(db, url2, use_type="blog")
    assert art3.id != art.id

    # Check ArticleUse (re-query via session)
    use = db.scalar(select(ArticleUse).where(ArticleUse.article_id == art3.id))
    assert use is not None
    assert use.use_type == "blog"
    assert use.status == "idea"

    db.close()
