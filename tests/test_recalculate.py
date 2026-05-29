from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.models import Article, ScoreRun, Source
from scripts.recalculate_scores import parse_duration, recalculate


def test_parse_duration():
    assert parse_duration("7d") == timedelta(days=7)
    assert parse_duration("24h") == timedelta(hours=24)
    assert parse_duration("30m") == timedelta(minutes=30)


def _seed(db):
    src = Source(
        slug="s", name="S", url="https://s", kind="rss", source_type="official_blog",
        topic="ai", trust_score=0.9, source_priority=0.8,
    )
    db.add(src)
    db.flush()
    art = Article(
        source_id=src.id,
        title="Agentic AI agent breakthrough in LLM orchestration",
        raw_title="Agentic AI agent breakthrough in LLM orchestration",
        normalized_title="agentic ai agent breakthrough in llm orchestration",
        original_url="https://s/a", canonical_url="https://s/a",
        dedup_hash="d1", content_hash="c1", language="en", country_scope="global",
        topic="ai", urgency="normal", reading_time_minutes=1, scraping_method="rss",
        status="new", final_score=0.0, fetched_at=datetime.now(timezone.utc),
    )
    db.add(art)
    db.commit()
    return art.id


def test_dry_run_writes_nothing(db_factory):
    db = db_factory()
    art_id = _seed(db)
    db.close()

    res = recalculate(session_factory=db_factory, all=True, dry_run=True)
    assert res["dry_run"] is True
    assert res["matched"] == 1
    assert res["changed"] == 1  # 0.0 -> a real score

    db = db_factory()
    assert db.scalar(select(func.count()).select_from(ScoreRun)) == 0
    assert db.get(Article, art_id).final_score == 0.0
    db.close()


def test_apply_updates_score_and_appends_run(db_factory):
    db = db_factory()
    art_id = _seed(db)
    db.close()

    res = recalculate(session_factory=db_factory, all=True)
    assert res["changed"] == 1

    db = db_factory()
    art = db.get(Article, art_id)
    assert art.final_score > 0.0
    assert "agentic-ai" in [t.name for t in art.tags]
    runs = db.scalar(
        select(func.count()).select_from(ScoreRun).where(ScoreRun.article_id == art_id)
    )
    assert runs == 1
    db.close()
