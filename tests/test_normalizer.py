import re

from app.services.normalizer import (
    canonicalize,
    content_hash,
    dedup_hash,
    normalized_title,
)


def test_canonicalize_strips_tracking_sorts_and_normalizes_url():
    url = (
        "HTTPS://Example.COM:443/news/story/"
        "?b=2&utm_source=x&a=1&fbclid=abc&Ref=home&keep=yes#section"
    )

    assert canonicalize(url) == "https://example.com/news/story?a=1&b=2&keep=yes"


def test_canonicalize_keeps_meaningful_params_and_non_default_port():
    url = "http://Example.com:8080/path/?z=9&gclid=x&q=search&utm_medium=email"

    assert canonicalize(url) == "http://example.com:8080/path?q=search&z=9"


def test_canonicalize_keeps_root_slash_and_handles_empty_url():
    assert canonicalize("HTTP://Example.COM:80/?b=2&a=1") == "http://example.com/?a=1&b=2"
    assert canonicalize("") == ""
    assert canonicalize(None) == ""


def test_dedup_hash_is_deterministic_64_hex():
    first = dedup_hash("https://example.com/news?a=1")
    second = dedup_hash("https://example.com/news?a=1")

    assert first == second
    assert re.fullmatch(r"[0-9a-f]{64}", first)


def test_normalized_title_strips_accents_lowercases_and_collapses_whitespace():
    assert normalized_title("  Bogotá\tNEWS\nToday  ") == "bogota news today"
    assert normalized_title("") == ""
    assert normalized_title(None) == ""


def test_content_hash_is_stable_and_changes_when_summary_changes():
    first = content_hash("Bogotá News", "summary")
    second = content_hash("Bogotá News", "summary")
    changed = content_hash("Bogotá News", "different")

    assert first == second
    assert first != changed


def test_content_hash_truncates_summary_at_1000_chars():
    base = "a" * 1000
    assert content_hash("Title", base + "x") == content_hash("Title", base + "y")
