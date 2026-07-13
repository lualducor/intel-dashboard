import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import yaml


@dataclass
class Interests:
    keywords: dict            # bucket_name -> {"weight": float, "terms": [str, ...]}
    categories_priority: dict # category_name -> float
    bucket_to_category: dict  # bucket_name -> category_name


def load_interests(path: str) -> Interests:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Interests(
        keywords=data.get("keywords", {}),
        categories_priority=data.get("categories_priority", {}),
        bucket_to_category=data.get("bucket_to_category", {})
    )


def _norm(text: str) -> str:
    # NFD accent-strip
    text = unicodedata.normalize('NFD', text)
    text = "".join(c for c in text if unicodedata.category(c) != 'Mn')
    # Lowercase
    text = text.lower()
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


@lru_cache(maxsize=2048)
def _term_pattern(normalized_term: str) -> re.Pattern[str]:
    """Compile a whole-word/phrase matcher for an already-normalized term."""
    phrase = r"\s+".join(re.escape(part) for part in normalized_term.split())
    return re.compile(rf"(?<!\w){phrase}(?!\w)")


def _matches_term(haystack: str, term: str) -> bool:
    normalized_term = _norm(term)
    return bool(normalized_term and _term_pattern(normalized_term).search(haystack))


def match_buckets(
    title: str,
    summary: str | None,
    interests: Interests,
    *,
    topic: str | None = None,
) -> list[tuple[str, float]]:
    haystack = _norm(title + " " + (summary or ""))
    results = []
    for bucket_name, info in interests.keywords.items():
        allowed_topics = info.get("topics")
        if allowed_topics and topic not in allowed_topics:
            continue
        weight = info.get("weight", 0.0)
        terms = info.get("terms", [])
        if any(_matches_term(haystack, term) for term in terms):
            results.append((bucket_name, weight))
    return results


def classify_category(
    matched_bucket_names: list[str], interests: Interests, *, topic: str
) -> str:
    if topic == "horoscope":
        return "horoscope"

    candidate_categories = []
    for bucket_name in matched_bucket_names:
        category = interests.bucket_to_category.get(bucket_name, "general")
        candidate_categories.append(category)

    if not candidate_categories:
        return "general"

    # Pick the one with the HIGHEST interests.categories_priority value
    best_category = "general"
    max_priority = -1.0

    for cat in candidate_categories:
        priority = interests.categories_priority.get(cat, 0.0)
        if priority > max_priority:
            max_priority = priority
            best_category = cat

    return best_category


def tag_article(
    title: str, summary: str | None, interests: Interests, *, topic: str
) -> tuple[list[str], str]:
    matched = match_buckets(title, summary, interests, topic=topic)
    tags = [name for name, _ in matched]
    category = classify_category(tags, interests, topic=topic)
    return (tags, category)
