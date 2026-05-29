"""Deterministic v1 scorer (PLAN.md §6.1).

final_score (v1_base) =
    0.20 * source_score        # 0.7*trust + 0.3*priority
  + 0.20 * freshness_score     # exp(-hours_since_published / 36)
  + 0.20 * keyword_score       # saturating sum of matched bucket weights
  + 0.10 * category_score      # categories_priority[category]
  + 0.20 * user_feedback_score # affinity maps (cold-start floor) — supplied by feedback.py
  + 0.10 * novelty_score       # 1 - max bigram-Jaccard vs recent 24h normalized_titles

Every score has an explanation and is recorded in a score_runs row (done by ingest).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

SCORE_VERSION = "v1_base"

WEIGHTS: dict[str, float] = {
    "source": 0.20,
    "freshness": 0.20,
    "keyword": 0.20,
    "category": 0.10,
    "feedback": 0.20,
    "novelty": 0.10,
}

# keyword_score saturation constant: 1 - exp(-raw / _KEYWORD_K). Lower K = faster saturation.
_KEYWORD_K = 1.5
_FRESHNESS_TAU_HOURS = 36.0


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass
class SubScores:
    source_score: float
    freshness_score: float
    keyword_score: float
    category_score: float
    user_feedback_score: float
    novelty_score: float


def source_score(trust_score: float, source_priority: float) -> float:
    return _clamp(0.7 * trust_score + 0.3 * source_priority)


def freshness_score(published_at: datetime | None, now: datetime) -> float:
    if published_at is None:
        return 0.5
    hours = (now - published_at).total_seconds() / 3600.0
    if hours < 0:  # future-dated feed item — treat as brand new
        hours = 0.0
    return _clamp(math.exp(-hours / _FRESHNESS_TAU_HOURS))


def keyword_score(matched_weights: list[float]) -> float:
    raw = sum(w for w in matched_weights if w > 0)
    if raw <= 0:
        return 0.0
    return _clamp(1.0 - math.exp(-raw / _KEYWORD_K))


def category_score(category: str | None, categories_priority: dict[str, float]) -> float:
    if category and category in categories_priority:
        return _clamp(float(categories_priority[category]))
    return _clamp(float(categories_priority.get("general", 0.3)))


def _ngrams(text: str) -> set[tuple[str, ...]]:
    tokens = text.split()
    if not tokens:
        return set()
    if len(tokens) < 2:
        return {(tokens[0],)}
    return set(zip(tokens, tokens[1:]))


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def novelty_score(normalized_title: str, recent_titles: list[str]) -> float:
    """1 - max bigram-Jaccard vs recent normalized titles. 1.0 when nothing recent."""
    title_grams = _ngrams(normalized_title)
    if not title_grams or not recent_titles:
        return 1.0
    max_sim = 0.0
    for other in recent_titles:
        sim = _jaccard(title_grams, _ngrams(other))
        if sim > max_sim:
            max_sim = sim
    return _clamp(1.0 - max_sim)


def combine(sub: SubScores) -> float:
    total = (
        WEIGHTS["source"] * sub.source_score
        + WEIGHTS["freshness"] * sub.freshness_score
        + WEIGHTS["keyword"] * sub.keyword_score
        + WEIGHTS["category"] * sub.category_score
        + WEIGHTS["feedback"] * sub.user_feedback_score
        + WEIGHTS["novelty"] * sub.novelty_score
    )
    return _clamp(total)


def build_explanation(
    *,
    trust_score: float,
    hours_since_published: float | None,
    tags: list[str],
    final: float,
) -> str:
    parts: list[str] = []
    if trust_score >= 0.85:
        parts.append(f"high source trust ({trust_score:.2f})")
    if hours_since_published is not None and hours_since_published <= 6:
        parts.append(f"fresh ({round(hours_since_published)}h ago)")
    if tags:
        parts.append("matches: " + ", ".join(tags[:3]))
    if not parts:
        return "low signal"
    return ", ".join(parts)
