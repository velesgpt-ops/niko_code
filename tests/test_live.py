"""
Живые интеграционные тесты — выполняют реальные запросы в интернет.

Запуск:
    pytest tests/test_live.py -v
    pytest tests/test_live.py -v -k test_live_search
"""

import json
import os
import tempfile

import pytest

from google_search_scraper.core import SearchAndScrape
from google_search_scraper.scraper import PageScraper
from google_search_scraper.search_providers import DuckDuckGoProvider


# --- Живой тест DuckDuckGo поиска ---


class TestLiveDuckDuckGo:
    """Реальный поиск через DuckDuckGo (бесплатно, без ключей)."""

    def test_live_search(self):
        """Поиск возвращает результаты с заполненными полями."""
        provider = DuckDuckGoProvider()
        results = provider.search("Python programming language", num_results=5)

        assert len(results) >= 1, "DuckDuckGo не вернул результатов"
        for r in results:
            assert r.url.startswith("http"), f"Невалидный URL: {r.url}"
            assert len(r.title) > 0, "Пустой заголовок"


# --- Живой тест скрапера ---


class TestLivePageScraper:
    """Реальное скачивание и парсинг веб-страниц."""

    def test_live_scrape_single_url(self):
        """Скрапинг одной известной страницы."""
        scraper = PageScraper(timeout=20)
        result = scraper.scrape_url("https://httpbin.org/html")

        assert result.success is True, f"Ошибка скрапинга: {result.error}"
        assert result.word_count > 0, "Не извлечён текст"
        assert len(result.title) > 0 or len(result.text) > 0

    def test_live_scrape_multiple_urls(self):
        """Параллельный скрапинг нескольких URL."""
        urls = [
            "https://httpbin.org/html",
            "https://example.com",
        ]
        scraper = PageScraper(timeout=20, max_workers=3)
        results = scraper.scrape_urls(urls)

        assert len(results) == len(urls)
        successful = [r for r in results if r.success]
        assert len(successful) >= 1, "Ни одна страница не скачалась"

    def test_live_scrape_non_html(self):
        """Скрапер корректно обрабатывает не-HTML ответ."""
        scraper = PageScraper(timeout=20)
        result = scraper.scrape_url("https://httpbin.org/json")

        assert result.success is False
        assert "Not HTML" in result.error


# --- Живой полный цикл ---


class TestLiveSearchAndScrape:
    """Полный цикл: поиск → скрапинг → сохранение."""

    def test_live_full_cycle(self):
        """Поиск + скрапинг 3 результатов."""
        engine = SearchAndScrape(
            provider=DuckDuckGoProvider(),
            scraper=PageScraper(timeout=20, max_workers=3),
            num_results=3,
        )
        result = engine.run("Python tutorial")

        assert result["query"] == "Python tutorial"
        assert result["total_results"] >= 1
        assert result["scraped_ok"] >= 1, "Ни одна страница не скачалась успешно"
        assert len(result["results"]) >= 1

        # Проверим структуру первого результата
        first = result["results"][0]
        assert "url" in first
        assert "search_title" in first
        assert "text" in first

    def test_live_save_to_json(self):
        """Полный цикл с сохранением в JSON-файл."""
        engine = SearchAndScrape(
            provider=DuckDuckGoProvider(),
            scraper=PageScraper(timeout=20, max_workers=3),
            num_results=3,
        )

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = f.name

        try:
            saved_path = engine.run_and_save("Python requests library", output_path=tmp_path)
            assert os.path.exists(saved_path)

            with open(saved_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert data["query"] == "Python requests library"
            assert len(data["results"]) >= 1
            assert data["scraped_ok"] >= 1

            # Проверим что JSON валидный и содержит текст
            has_text = any(r["word_count"] > 0 for r in data["results"] if r["success"])
            assert has_text, "Ни один результат не содержит текста"
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
