from pathlib import Path

import pytest

from app.services.tagger import load_interests, match_buckets, tag_article


@pytest.fixture
def interests():
    path = Path(__file__).resolve().parents[1] / "app" / "interests.yaml"
    return load_interests(str(path))


def test_tagger_agentic_ai(interests):
    title = "New agentic AI agent framework"
    tags, category = tag_article(title, None, interests, topic="ai")
    assert "agentic-ai" in tags
    assert category == "agentic_ai"


def test_tagger_local_first(interests):
    title = "Running models with ollama"
    tags, category = tag_article(title, None, interests, topic="ai")
    assert "local-first" in tags
    assert category == "ai_infrastructure"


def test_tagger_colombia_tech(interests):
    title = "Nuevas startups en Bogotá"
    tags, category = tag_article(title, None, interests, topic="colombia")
    assert "colombia-tech" in tags
    assert category == "colombia_tech"


def test_tagger_horoscope(interests):
    title = "AI for everything"
    tags, category = tag_article(title, None, interests, topic="horoscope")
    # Even if it matches AI, topic="horoscope" forces category "horoscope"
    assert "ai-systems" not in tags  # "ai" alone doesn't match "ai system"
    assert category == "horoscope"


def test_tagger_no_matches(interests):
    title = "Something completely unrelated"
    tags, category = tag_article(title, None, interests, topic="misc")
    assert tags == []
    assert category == "general"


def test_tagger_normalization(interests):
    # Test accent stripping
    title = "MÉDELLÍN tech"
    tags, category = tag_article(title, None, interests, topic="colombia")
    assert "colombia-tech" in tags


def test_colombia_place_name_alone_is_not_a_tech_signal(interests):
    title = (
        "Transportaban insumos químicos en camiones en Bogotá: "
        "así cayó un cargamento para producir cocaína"
    )
    tags, category = tag_article(title, None, interests, topic="colombia")

    assert "colombia-tech" not in tags
    assert category == "general"


@pytest.mark.parametrize(
    "title",
    [
        "Clínicas clandestinas reabren en Bogotá",
        "La capital anuncia nuevas medidas",
        "El presidente habló sobre la identidad ciudadana",
    ],
)
def test_short_developer_terms_do_not_match_inside_words(interests, title):
    tags, _ = tag_article(title, None, interests, topic="colombia")

    assert "developer-tooling" not in tags


def test_short_developer_terms_still_match_as_words(interests):
    matches = match_buckets(
        "A new API and CLI for developers",
        None,
        interests,
        topic="ai",
    )

    assert "developer-tooling" in {name for name, _ in matches}
