import pytest
from app.models import Article, ArticleUse, Source
from app.services import queues
from app.config import get_settings

def test_queue_assignment_logic(db_factory):
    db = db_factory()
    settings = get_settings()
    
    # Setup: Create a source
    source = Source(
        slug="tech-news",
        name="Tech News",
        url="https://tech.news",
        kind="rss",
        source_type="news",
        topic="ai",
        active=True
    )
    db.add(source)
    db.commit()

    def create_article(title, score, status="new", topic="ai", dedup_suffix=""):
        return Article(
            source_id=source.id,
            title=title,
            raw_title=title,
            normalized_title=title.lower(),
            original_url=f"https://tech.news/{title.replace(' ', '-')}",
            canonical_url=f"https://tech.news/{title.replace(' ', '-')}",
            dedup_hash=f"hash-{title}-{dedup_suffix}",
            content_hash=f"content-{title}",
            language="en",
            country_scope="global",
            topic=topic,
            urgency="normal",
            reading_time_minutes=5,
            scraping_method="rss",
            final_score=score,
            status=status
        )

    # 1. AI, new, score 0.8 -> must_read (>= 0.70)
    a1 = create_article("Must Read AI", 0.8)
    db.add(a1)
    
    # 2. AI, new, score 0.5 -> maybe_useful (0.40..0.70)
    a2 = create_article("Maybe Useful AI", 0.5)
    db.add(a2)
    
    # 3. AI, new, score 0.2 -> noise (< 0.40)
    a3 = create_article("Noise AI", 0.2)
    db.add(a3)
    
    # 4. AI, ignored -> noise
    a4 = create_article("Ignored AI", 0.9, status="ignored")
    db.add(a4)
    
    # 5. AI, saved + ArticleUse(status='idea') -> for_content
    a5 = create_article("For Content AI", 0.6, status="saved", dedup_suffix="5")
    db.add(a5)
    db.flush()
    db.add(ArticleUse(article_id=a5.id, use_type="newsletter", status="idea"))
    
    # 6. AI, saved but NO ArticleUse -> NOT for_content
    a6 = create_article("Saved No Use AI", 0.6, status="saved", dedup_suffix="6")
    db.add(a6)
    
    db.commit()

    # Verify must_read
    must_read = queues.feed(db, settings, queue="must_read")
    assert len(must_read) == 1
    assert must_read[0].title == "Must Read AI"

    # Verify maybe_useful
    maybe_useful = queues.feed(db, settings, queue="maybe_useful")
    assert len(maybe_useful) == 1
    assert maybe_useful[0].title == "Maybe Useful AI"

    # Verify noise
    noise = queues.feed(db, settings, queue="noise")
    assert len(noise) == 2
    titles = [a.title for a in noise]
    assert "Noise AI" in titles
    assert "Ignored AI" in titles

    # Verify for_content
    for_content = queues.feed(db, settings, queue="for_content")
    assert len(for_content) == 1
    assert for_content[0].title == "For Content AI"

    # Pagination is deterministic and bounded.
    first_page = queues.feed(db, settings, queue="noise", limit=1)
    second_page = queues.feed(db, settings, queue="noise", limit=1, offset=1)
    assert len(first_page) == len(second_page) == 1
    assert first_page[0].id != second_page[0].id

    # Verify queue_counts
    counts = queues.queue_counts(db, settings)
    assert counts["must_read"] == 1
    assert counts["maybe_useful"] == 1
    assert counts["for_content"] == 1
    assert counts["noise"] == 2
