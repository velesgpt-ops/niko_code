"""
Тесты модуля google_search_scraper с моками (без реального интернета).
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from google_search_scraper.core import SearchAndScrape, create_provider
from google_search_scraper.scraper import PageScraper, ScrapedPage
from google_search_scraper.search_providers import (
    DuckDuckGoProvider,
    GoogleCSEProvider,
    SearchResult,
    SerpAPIProvider,
)


# --- Фикстуры ---

SAMPLE_HTML = """
<html>
<head><title>Test Page Title</title></head>
<body>
    <nav><a href="/">Home</a></nav>
    <main>
        <h1>Main Heading</h1>
        <p>This is a paragraph with enough text to be captured by the scraper module for testing purposes.</p>
        <p>Another paragraph with important content that should also be extracted by the content parser.</p>
        <p>Third paragraph contains even more details about the topic being discussed in this test page.</p>
    </main>
    <footer>Footer content</footer>
    <script>var x = 1;</script>
</body>
</html>
"""

FAKE_SEARCH_RESULTS = [
    SearchResult(title=f"Result {i}", url=f"https://example.com/page{i}", snippet=f"Snippet {i}")
    for i in range(5)
]


# --- Тесты извлечения контента ---


class TestPageScraper:
    def test_extract_content(self):
        """Тест извлечения текста из HTML."""
        scraper = PageScraper()
        title, text = scraper._extract_content(SAMPLE_HTML)

        assert title == "Test Page Title"
        assert "paragraph with enough text" in text
        # nav и footer должны быть удалены
        assert "Footer content" not in text
        assert "var x = 1" not in text

    def test_extract_content_no_main(self):
        """Тест извлечения из HTML без тега <main>."""
        html = """
        <html><head><title>Simple</title></head>
        <body>
            <p>This is a simple page with just some body content that is long enough to be captured.</p>
            <p>Second paragraph also has some meaningful content for extraction by the scraper module.</p>
            <p>Third paragraph rounds out the content with additional information for testing purposes here.</p>
        </body>
        </html>
        """
        scraper = PageScraper()
        title, text = scraper._extract_content(html)

        assert title == "Simple"
        assert "simple page" in text

    @patch("google_search_scraper.scraper.requests.Session")
    def test_scrape_url_success(self, mock_session_cls):
        """Тест успешного скрапинга URL."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_resp.text = SAMPLE_HTML
        mock_resp.apparent_encoding = "utf-8"
        mock_resp.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        scraper = PageScraper()
        scraper.session = mock_session
        result = scraper.scrape_url("https://example.com")

        assert result.success is True
        assert result.title == "Test Page Title"
        assert result.word_count > 0
        assert "paragraph" in result.text

    @patch("google_search_scraper.scraper.requests.Session")
    def test_scrape_url_timeout(self, mock_session_cls):
        """Тест обработки таймаута."""
        import requests

        mock_session = MagicMock()
        mock_session.get.side_effect = requests.Timeout("Connection timed out")
        mock_session_cls.return_value = mock_session

        scraper = PageScraper()
        scraper.session = mock_session
        result = scraper.scrape_url("https://slow-site.com")

        assert result.success is False
        assert "Timeout" in result.error

    @patch("google_search_scraper.scraper.requests.Session")
    def test_scrape_url_not_html(self, mock_session_cls):
        """Тест обработки не-HTML контента."""
        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Type": "application/pdf"}
        mock_resp.raise_for_status = MagicMock()

        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        scraper = PageScraper()
        scraper.session = mock_session
        result = scraper.scrape_url("https://example.com/file.pdf")

        assert result.success is False
        assert "Not HTML" in result.error

    @patch.object(PageScraper, "scrape_url")
    def test_scrape_urls_parallel(self, mock_scrape):
        """Тест параллельного скрапинга с сохранением порядка."""
        urls = ["https://example.com/1", "https://example.com/2", "https://example.com/3"]

        def fake_scrape(url):
            return ScrapedPage(url=url, title=f"Page {url[-1]}", text="content", word_count=1)

        mock_scrape.side_effect = fake_scrape

        scraper = PageScraper()
        results = scraper.scrape_urls(urls)

        assert len(results) == 3
        # Проверяем что порядок сохранён
        assert results[0].url == urls[0]
        assert results[1].url == urls[1]
        assert results[2].url == urls[2]


# --- Тесты провайдеров поиска ---


class TestDuckDuckGoProvider:
    @patch("duckduckgo_search.DDGS")
    def test_search(self, mock_ddgs_cls):
        """Тест DuckDuckGo провайдера."""
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = [
            {"title": "Result 1", "href": "https://example.com/1", "body": "Snippet 1"},
            {"title": "Result 2", "href": "https://example.com/2", "body": "Snippet 2"},
        ]
        mock_ddgs_cls.return_value = mock_ddgs

        provider = DuckDuckGoProvider()
        results = provider.search("test query", num_results=2)

        assert len(results) == 2
        assert results[0].title == "Result 1"
        assert results[0].url == "https://example.com/1"
        assert results[1].snippet == "Snippet 2"


class TestGoogleCSEProvider:
    @patch("google_search_scraper.search_providers.requests.get")
    def test_search(self, mock_get):
        """Тест Google CSE провайдера."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "items": [
                {"title": "CSE Result 1", "link": "https://example.com/cse1", "snippet": "CSE snippet"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        provider = GoogleCSEProvider(api_key="fake-key", cx="fake-cx")
        results = provider.search("test", num_results=1)

        assert len(results) == 1
        assert results[0].title == "CSE Result 1"
        mock_get.assert_called_once()


class TestSerpAPIProvider:
    @patch("google_search_scraper.search_providers.requests.get")
    def test_search(self, mock_get):
        """Тест SerpAPI провайдера."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "organic_results": [
                {"title": "Serp Result", "link": "https://example.com/serp", "snippet": "Serp snippet"},
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        provider = SerpAPIProvider(api_key="fake-key")
        results = provider.search("test", num_results=1)

        assert len(results) == 1
        assert results[0].title == "Serp Result"


# --- Тесты основного модуля ---


class TestSearchAndScrape:
    def test_run(self):
        """Тест полного цикла поиск + скрапинг."""
        mock_provider = MagicMock()
        mock_provider.search.return_value = FAKE_SEARCH_RESULTS

        mock_scraper = MagicMock()
        mock_scraper.scrape_urls.return_value = [
            ScrapedPage(url=r.url, title=f"Page {i}", text="Content here", word_count=2)
            for i, r in enumerate(FAKE_SEARCH_RESULTS)
        ]

        engine = SearchAndScrape(provider=mock_provider, scraper=mock_scraper, num_results=5)
        result = engine.run("test query")

        assert result["query"] == "test query"
        assert result["total_results"] == 5
        assert result["scraped_ok"] == 5
        assert result["scraped_fail"] == 0
        assert len(result["results"]) == 5
        assert result["results"][0]["search_title"] == "Result 0"
        assert result["results"][0]["page_title"] == "Page 0"

    def test_run_and_save(self):
        """Тест сохранения результатов в JSON."""
        mock_provider = MagicMock()
        mock_provider.search.return_value = FAKE_SEARCH_RESULTS[:2]

        mock_scraper = MagicMock()
        mock_scraper.scrape_urls.return_value = [
            ScrapedPage(url=r.url, title="T", text="Text", word_count=1)
            for r in FAKE_SEARCH_RESULTS[:2]
        ]

        engine = SearchAndScrape(provider=mock_provider, scraper=mock_scraper, num_results=2)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = f.name

        try:
            saved_path = engine.run_and_save("test", output_path=tmp_path)
            assert saved_path == tmp_path

            with open(tmp_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert data["query"] == "test"
            assert len(data["results"]) == 2
        finally:
            os.unlink(tmp_path)

    def test_run_with_failures(self):
        """Тест с частично неудачным скрапингом."""
        mock_provider = MagicMock()
        mock_provider.search.return_value = FAKE_SEARCH_RESULTS[:3]

        mock_scraper = MagicMock()
        mock_scraper.scrape_urls.return_value = [
            ScrapedPage(url=FAKE_SEARCH_RESULTS[0].url, title="OK", text="Text", word_count=1),
            ScrapedPage(url=FAKE_SEARCH_RESULTS[1].url, success=False, error="Timeout"),
            ScrapedPage(url=FAKE_SEARCH_RESULTS[2].url, title="OK2", text="Text2", word_count=1),
        ]

        engine = SearchAndScrape(provider=mock_provider, scraper=mock_scraper, num_results=3)
        result = engine.run("test")

        assert result["scraped_ok"] == 2
        assert result["scraped_fail"] == 1


# --- Тесты фабрики провайдеров ---


class TestCreateProvider:
    def test_duckduckgo(self):
        provider = create_provider("duckduckgo")
        assert isinstance(provider, DuckDuckGoProvider)

    def test_google_cse(self):
        provider = create_provider("google_cse", api_key="key", cx="cx-id")
        assert isinstance(provider, GoogleCSEProvider)

    def test_serpapi(self):
        provider = create_provider("serpapi", api_key="key")
        assert isinstance(provider, SerpAPIProvider)

    def test_google_cse_missing_key(self):
        with pytest.raises(ValueError, match="api_key"):
            create_provider("google_cse")

    def test_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            create_provider("yahoo")
