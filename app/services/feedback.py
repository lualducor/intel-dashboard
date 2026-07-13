"""User-feedback affinity (PLAN.md §6.1).

Builds affinity maps over the last 90 days of user_actions and derives a
user_feedback_score with a cold-start floor. The 0.20 weight on this factor is
fixed (in scorer.WEIGHTS); only the score value ramps from the cold-start floor
to a real signal once enough actions exist.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Article, UserAction

# Signed weights per action type (recs doc §7.3, adapted). Positive = affinity up.
ACTION_WEIGHTS: dict[str, float] = {
    "useful": 1.0,
    "used_for_content": 1.0,
    "for_content": 1.0,
    "important": 0.8,
    "save": 0.5,
    "followup": 0.5,
    "read": 0.2,
    "archive": -0.2,
    "ignore": -0.8,
    "not_relevant": -1.0,
}

_AFFINITY_WINDOW_DAYS = 90
_AFFINITY_TANH_K = 3.0


def _affinity_from_raw(raw: float) -> float:
    """Map a signed raw weight sum to a 0..1 affinity centered on 0.5 (neutral)."""
    return max(0.0, min(1.0, 0.5 + 0.5 * math.tanh(raw / _AFFINITY_TANH_K)))


@dataclass
class AffinityMaps:
    source_aff: dict[int, float] = field(default_factory=dict)
    tag_aff: dict[int, float] = field(default_factory=dict)
    category_aff: dict[str, float] = field(default_factory=dict)
    total_actions: int = 0


def compute_affinity_maps(db: Session, *, now: datetime | None = None) -> AffinityMaps:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=_AFFINITY_WINDOW_DAYS)

    rows = db.execute(
        select(UserAction, Article)
        .join(Article, UserAction.article_id == Article.id)
        .where(UserAction.created_at >= cutoff)
    ).all()

    source_raw: dict[int, float] = {}
    tag_raw: dict[int, float] = {}
    category_raw: dict[str, float] = {}
    total = 0

    for action, article in rows:
        weight = ACTION_WEIGHTS.get(action.action)
        if weight is None:
            continue
        total += 1
        source_raw[article.source_id] = source_raw.get(article.source_id, 0.0) + weight
        if article.category:
            category_raw[article.category] = (
                category_raw.get(article.category, 0.0) + weight
            )
        for tag in article.tags:
            tag_raw[tag.id] = tag_raw.get(tag.id, 0.0) + weight

    return AffinityMaps(
        source_aff={k: _affinity_from_raw(v) for k, v in source_raw.items()},
        tag_aff={k: _affinity_from_raw(v) for k, v in tag_raw.items()},
        category_aff={k: _affinity_from_raw(v) for k, v in category_raw.items()},
        total_actions=total,
    )


def user_feedback_score(
    *,
    source_id: int,
    tag_ids: list[int],
    category: str | None,
    maps: AffinityMaps,
    cold_floor: float,
    ramp_at: int,
) -> float:
    """Blend from the cold-start floor toward learned affinity as actions accrue."""
    if maps.total_actions == 0:
        return cold_floor

    source_aff = maps.source_aff.get(source_id, 0.5)
    if tag_ids:
        tag_aff = sum(maps.tag_aff.get(t, 0.5) for t in tag_ids) / len(tag_ids)
    else:
        tag_aff = 0.5
    category_aff = maps.category_aff.get(category, 0.5) if category else 0.5

    affinity = 0.25 * source_aff + 0.25 * tag_aff + 0.25 * category_aff + 0.25 * 0.5
    learned = max(0.0, min(1.0, 0.3 + (affinity - 0.5)))
    progress = min(1.0, maps.total_actions / max(1, ramp_at))
    return cold_floor + progress * (learned - cold_floor)
