import math
from datetime import datetime, timedelta, timezone

from app.services import scorer


def test_source_score():
    assert abs(scorer.source_score(0.9, 0.8) - 0.87) < 1e-9


def test_freshness_score():
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    assert scorer.freshness_score(None, now) == 0.5
    assert abs(scorer.freshness_score(now - timedelta(hours=36), now) - math.exp(-1)) < 1e-6
    assert scorer.freshness_score(now, now) == 1.0
    assert scorer.freshness_score(now + timedelta(hours=5), now) == 1.0  # future -> 1.0


def test_keyword_score_monotonic():
    assert scorer.keyword_score([]) == 0.0
    one = scorer.keyword_score([1.0])
    two = scorer.keyword_score([1.0, 1.2])
    assert 0.0 < one < two <= 1.0


def test_category_score():
    cp = {"agentic_ai": 0.95, "general": 0.3}
    assert scorer.category_score("agentic_ai", cp) == 0.95
    assert scorer.category_score(None, cp) == 0.3
    assert scorer.category_score("missing", cp) == 0.3


def test_novelty_score():
    assert scorer.novelty_score("agentic ai breakthrough", []) == 1.0
    assert scorer.novelty_score("agentic ai breakthrough", ["agentic ai breakthrough"]) == 0.0
    partial = scorer.novelty_score("agentic ai systems", ["agentic ai breakthrough"])
    assert 0.0 < partial < 1.0


def test_combine_and_explanation():
    sub = scorer.SubScores(0.87, 1.0, 0.5, 0.95, 0.3, 1.0)
    expected = 0.2 * 0.87 + 0.2 * 1.0 + 0.2 * 0.5 + 0.1 * 0.95 + 0.2 * 0.3 + 0.1 * 1.0
    assert abs(scorer.combine(sub) - expected) < 1e-9

    expl = scorer.build_explanation(
        trust_score=0.95,
        hours_since_published=2,
        tags=["agentic-ai", "llm-orchestration"],
        final=0.8,
    )
    assert "high source trust" in expl
    assert "fresh" in expl
    assert "agentic-ai" in expl

    low = scorer.build_explanation(
        trust_score=0.5, hours_since_published=None, tags=[], final=0.1
    )
    assert low == "low signal"
