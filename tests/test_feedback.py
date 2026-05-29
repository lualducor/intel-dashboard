from app.models import Article, Source, UserAction
from app.services.feedback import compute_affinity_maps, user_feedback_score


def _make_article(db, *, category="agentic_ai"):
    src = Source(
        slug="s",
        name="S",
        url="https://s",
        kind="rss",
        source_type="official_blog",
        topic="ai",
        trust_score=0.9,
        source_priority=0.8,
    )
    db.add(src)
    db.flush()
    art = Article(
        source_id=src.id,
        title="t",
        raw_title="t",
        normalized_title="t",
        original_url="https://s/a",
        canonical_url="https://s/a",
        dedup_hash="d",
        content_hash="c",
        language="en",
        country_scope="global",
        topic="ai",
        category=category,
        urgency="normal",
        reading_time_minutes=1,
        scraping_method="rss",
    )
    db.add(art)
    db.flush()
    return src, art


def test_cold_start_returns_floor(db_factory):
    db = db_factory()
    maps = compute_affinity_maps(db)
    assert maps.total_actions == 0
    score = user_feedback_score(
        source_id=1, tag_ids=[], category=None, maps=maps, cold_floor=0.3, ramp_at=50
    )
    assert score == 0.3
    db.close()


def test_positive_affinity_ramps(db_factory):
    db = db_factory()
    src, art = _make_article(db)
    for _ in range(60):
        db.add(UserAction(article_id=art.id, action="useful"))
    db.commit()

    maps = compute_affinity_maps(db)
    assert maps.total_actions == 60
    assert maps.source_aff[src.id] > 0.5
    assert maps.category_aff["agentic_ai"] > 0.5

    score = user_feedback_score(
        source_id=src.id,
        tag_ids=[],
        category="agentic_ai",
        maps=maps,
        cold_floor=0.3,
        ramp_at=50,
    )
    assert score > 0.3
    db.close()


def test_negative_actions_lower_affinity(db_factory):
    db = db_factory()
    src, art = _make_article(db, category="regulation")
    for _ in range(60):
        db.add(UserAction(article_id=art.id, action="not_relevant"))
    db.commit()
    maps = compute_affinity_maps(db)
    assert maps.source_aff[src.id] < 0.5
    db.close()
