import httpx
import respx

from app.services.adapters import fetch_html_listing


async def test_html_listing_extracts_json_ld_and_article_cards():
    url = "https://news.example/latest"
    page = """<html><body><main>
    <script type="application/ld+json">{
      "@type":"NewsArticle", "headline":"Structured AI story",
      "url":"/structured", "datePublished":"2026-07-12T10:00:00Z",
      "description":"<p>Structured <strong>summary</strong></p>"
    }</script>
    <article><h2><a href="/card">Agent tooling story</a></h2>
      <time datetime="2026-07-11T09:00:00Z"></time><p>Card summary</p></article>
    </main></body></html>"""
    with respx.mock:
        respx.get(url).mock(return_value=httpx.Response(200, text=page))
        result = await fetch_html_listing(url, user_agent="test", timeout=5)

    assert len(result) == 2
    assert {item.title for item in result} == {
        "Structured AI story",
        "Agent tooling story",
    }
    assert all(item.link.startswith("https://news.example/") for item in result)
    structured = next(item for item in result if item.title == "Structured AI story")
    assert structured.summary == "Structured summary"
