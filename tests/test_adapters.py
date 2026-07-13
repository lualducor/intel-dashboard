import httpx
import pytest
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


@pytest.mark.parametrize(
    ("url", "page", "expected_title", "expected_date"),
    [
        (
            "https://www.anthropic.com/news",
            """<a href="/news/claude-update"><h2>Claude update</h2>
            <time>Jul 9, 2026</time><p>A safer and more capable model.</p></a>""",
            "Claude update",
            (2026, 7, 9),
        ),
        (
            "https://www.mintic.gov.co/portal/inicio/Sala-de-prensa/Noticias/",
            """<div class="recuadro"><div class="fecha">10 de julio de 2026</div>
            <div class="titulo"><a href="/portal/inicio/Sala-de-prensa/Noticias/439654:IA-publica">
            MinTIC publica nuevos modelos de IA</a></div></div>""",
            "MinTIC publica nuevos modelos de IA",
            (2026, 7, 10),
        ),
        (
            "https://ai.meta.com/blog/",
            """<div class="card"><h4>Research</h4><h4>Introducing a Meta AI model</h4>
            <p>Details about the new research model.</p><p>July 9, 2026</p>
            <a href="https://ai.meta.com/blog/new-model/">Learn More</a></div>""",
            "Introducing a Meta AI model",
            (2026, 7, 9),
        ),
        (
            "https://bogota.gov.co/busqueda?search_api_fulltext=tecnologia",
            """<div class="tarjeta tarjeta-3"><h2><a href="/mi-ciudad/educacion/tecnologia">
            Bogotá amplía su educación digital</a></h2><span class="views-field-created">
            07•Jul•2026</span><p>Nuevos programas tecnológicos para estudiantes.</p></div>""",
            "Bogotá amplía su educación digital",
            (2026, 7, 7),
        ),
        (
            "https://news.microsoft.com/source/topics/ai/",
            """<article><a href="https://news.microsoft.com/source/tag/ai/">AI</a>
            <h2><a href="https://blogs.microsoft.com/blog/2026/06/02/agent-platform/">
            Microsoft expands its agent platform</a></h2></article>""",
            "Microsoft expands its agent platform",
            (2026, 6, 2),
        ),
        (
            "https://www.afr.com/technology",
            """<div data-testid="StoryTileBase"><h3><a href="/technology/new-chip-20260713-p60abc">
            Australian lab unveils a faster AI chip</a></h3>
            <p data-pb-type="ab">The processor targets efficient local inference.</p>
            <span data-pb-type="au">Ada Engineer</span>
            <time datetime="Jul 13, 2026 – 10.30am">Jul 13, 2026</time></div>""",
            "Australian lab unveils a faster AI chip",
            (2026, 7, 13),
        ),
        (
            "https://r.jina.ai/https://www.radware.com/blog/",
            """Markdown Content:
            [![Image 3: Securing Autonomous AI Agents](https://www.radware.com/image.jpg)
            Agentic AI Security Securing Autonomous AI Agents Practical controls for enterprise agents.
            Radware **|**July 09, 2026](https://www.radware.com/blog/posts/securing-autonomous-ai-agents/)""",
            "Securing Autonomous AI Agents",
            (2026, 7, 9),
        ),
        (
            "https://tech.yahoo.com/",
            """<script>self.__next_f.push([1,"canonicalUrl":"https://tech.yahoo.com/computing/article/new-laptop-123.html","categoryLabel":"Computing","displayTime":"2026-07-13T12:30:00Z","headline":"A fast \\u0026 repairable laptop","provider":{}])</script>""",
            "A fast & repairable laptop",
            (2026, 7, 13),
        ),
    ],
)
async def test_known_site_adapters(url, page, expected_title, expected_date):
    with respx.mock:
        respx.get(url).mock(return_value=httpx.Response(200, text=page))
        result = await fetch_html_listing(url, user_agent="test", timeout=5)

    assert len(result) == 1
    assert result[0].title == expected_title
    assert (
        result[0].published_at.year,
        result[0].published_at.month,
        result[0].published_at.day,
    ) == expected_date


async def test_microsoft_ai_adapter_filters_non_ai_cards():
    url = "https://news.microsoft.com/source/topics/ai/"
    page = """<article><a href="https://news.microsoft.com/source/tag/ai/">AI</a>
    <h2><a href="https://blogs.microsoft.com/blog/2026/07/02/ai-engineering/">
    AI engineering that protects intelligence</a></h2></article>
    <article><a href="https://news.microsoft.com/source/tag/sustainability/">Sustainability</a>
    <h2><a href="https://example.com/water">Water story</a></h2></article>"""
    with respx.mock:
        respx.get(url).mock(return_value=httpx.Response(200, text=page))
        result = await fetch_html_listing(url, user_agent="test", timeout=5)

    assert len(result) == 1
    assert result[0].title == "AI engineering that protects intelligence"


async def test_afr_adapter_ignores_topic_navigation_links():
    url = "https://www.afr.com/technology"
    page = """<a href="/topic/artificial-intelligence-5ui">AI topic</a>
    <div data-testid="StoryTileBase"><h3><a href="/technology/ai-policy-20260712-p60enz">
    AI policy earns public scrutiny</a></h3><time datetime="Jul 12, 2026"></time></div>"""
    with respx.mock:
        respx.get(url).mock(return_value=httpx.Response(200, text=page))
        result = await fetch_html_listing(url, user_agent="test", timeout=5)

    assert len(result) == 1
    assert result[0].link == "https://www.afr.com/technology/ai-policy-20260712-p60enz"
