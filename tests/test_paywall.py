from app.services.paywall import is_paywalled, rewrite_link


def test_is_paywalled_returns_bool_flag():
    assert is_paywalled(True) is True
    assert is_paywalled(False) is False
    assert is_paywalled(1) is True
    assert is_paywalled(0) is False


def test_rewrite_link_prepends_prefix_when_present():
    assert rewrite_link("https://example.com/news", "https://archive.example/") == (
        "https://archive.example/https://example.com/news"
    )


def test_rewrite_link_returns_url_without_prefix():
    assert rewrite_link("https://example.com/news", "") == "https://example.com/news"
