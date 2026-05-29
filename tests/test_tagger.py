import pytest
from pathlib import Path
from app.services.tagger import load_interests, tag_article

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
    # colombia-tech maps to general in interests.yaml
    assert category == "general"

def test_tagger_horoscope(interests):
    title = "AI for everything"
    tags, category = tag_article(title, None, interests, topic="horoscope")
    # Even if it matches AI, topic="horoscope" forces category "horoscope"
    assert "ai-systems" not in tags # "ai" alone doesn't match "ai system"
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
