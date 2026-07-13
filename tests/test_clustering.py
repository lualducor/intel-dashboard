from datetime import datetime, timedelta, timezone

from app.models import Article, Source
from app.services.clustering import assign_story_cluster


def _article(source_id, suffix, title):
    return Article(
        source_id=source_id,
        title=title,
        raw_title=title,
        normalized_title=title.lower(),
        original_url=f"https://example.com/{suffix}",
        canonical_url=f"https://example.com/{suffix}",
        dedup_hash=f"cluster-{suffix}",
        content_hash=f"cluster-content-{suffix}",
        language="en",
        country_scope="global",
        topic="ai",
        urgency="normal",
        reading_time_minutes=1,
        scraping_method="rss",
        final_score=0.8,
        status="new",
    )


def test_assign_story_cluster_groups_similar_cross_source_titles(db_factory):
    db = db_factory()
    first_source = Source(
        slug="cluster-one", name="One", url="https://one.example", kind="rss",
        source_type="news", topic="ai"
    )
    second_source = Source(
        slug="cluster-two", name="Two", url="https://two.example", kind="rss",
        source_type="news", topic="ai"
    )
    db.add_all([first_source, second_source])
    db.flush()
    now = datetime.now(timezone.utc)
    first = _article(first_source.id, "one", "OpenAI launches a new agent platform")
    first.fetched_at = (now - timedelta(hours=1)).replace(tzinfo=None)
    second = _article(second_source.id, "two", "OpenAI launches new agent platform")
    second.fetched_at = now
    db.add_all([first, second])
    db.flush()

    cluster = assign_story_cluster(db, second, now=now)

    assert cluster is not None
    assert first.cluster_id == second.cluster_id == cluster.id
    assert cluster.source_count == 2
    db.close()
