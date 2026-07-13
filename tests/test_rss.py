import pytest
import respx
import httpx
from pathlib import Path
from app.services.rss import EmptyFeedError, fetch_rss

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
  <title>Test Feed</title>
  <link>http://example.com</link>
  <item>
    <title>Item 1</title>
    <link>http://example.com/item1</link>
    <description>Summary 1</description>
    <pubDate>Mon, 25 May 2026 10:00:00 +0000</pubDate>
    <author>Author 1</author>
  </item>
  <item>
    <title>Item 2</title>
    <link>http://example.com/item2</link>
  </item>
  <item>
    <title></title>
    <link></link>
  </item>
</channel>
</rss>
"""

@pytest.mark.asyncio
async def test_fetch_rss_parsing():
    url = "https://example.com/rss"
    with respx.mock:
        respx.get(url).mock(return_value=httpx.Response(200, content=SAMPLE_RSS))
        
        items = await fetch_rss(url, user_agent="test", timeout=5.0)
        
        assert len(items) == 2
        assert items[0].title == "Item 1"
        assert items[0].link == "http://example.com/item1"
        assert items[0].summary == "Summary 1"
        assert items[0].author == "Author 1"
        assert items[0].published_at is not None
        assert items[0].published_at.tzinfo is not None
        
        assert items[1].title == "Item 2"
        assert items[1].published_at is None

@pytest.mark.asyncio
async def test_fetch_rss_404():
    url = "https://example.com/404"
    with respx.mock:
        respx.get(url).mock(return_value=httpx.Response(404))
        
        with pytest.raises(httpx.HTTPStatusError):
            await fetch_rss(url, user_agent="test", timeout=5.0)

@pytest.mark.asyncio
async def test_fetch_rss_from_fixture():
    url = "https://anthropic.com/feed"
    fixture_path = Path(__file__).parent / "fixtures" / "feeds" / "anthropic_sample.xml"
    content = fixture_path.read_text()
    
    with respx.mock:
        respx.get(url).mock(return_value=httpx.Response(200, content=content))
        
        items = await fetch_rss(url, user_agent="test", timeout=5.0)
        
        assert len(items) == 1
        assert items[0].title == "Model Context Protocol"
        assert "MCP" in items[0].summary
        assert items[0].published_at is not None
        assert items[0].published_at.year == 2024


@pytest.mark.asyncio
async def test_fetch_rss_sends_cache_headers_and_handles_not_modified():
    url = "https://example.com/cached.xml"

    def responder(request):
        assert request.headers["if-none-match"] == '"feed-v1"'
        assert request.headers["if-modified-since"] == "Mon, 01 Jun 2026 00:00:00 GMT"
        return httpx.Response(304)

    with respx.mock:
        respx.get(url).mock(side_effect=responder)
        result = await fetch_rss(
            url,
            user_agent="test",
            timeout=5.0,
            etag='"feed-v1"',
            last_modified="Mon, 01 Jun 2026 00:00:00 GMT",
        )

    assert result.not_modified is True
    assert len(result) == 0


@pytest.mark.asyncio
async def test_fetch_rss_rejects_empty_feed():
    url = "https://example.com/empty.xml"
    empty = "<rss version='2.0'><channel><title>Empty</title></channel></rss>"
    with respx.mock:
        respx.get(url).mock(return_value=httpx.Response(200, text=empty))
        with pytest.raises(EmptyFeedError):
            await fetch_rss(url, user_agent="test", timeout=5.0)
