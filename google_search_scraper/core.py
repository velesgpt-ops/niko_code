"""
Основной модуль — объединяет поиск и скрапинг.
"""

import json
import logging
import os
from dataclasses import asdict
from datetime import datetime
from typing import Optional

from google_search_scraper.scraper import PageScraper, ScrapedPage
from google_search_scraper.search_providers import (
    DuckDuckGoProvider,
    GoogleCSEProvider,
    SearchProvider,
    SearchResult,
    SerpAPIProvider,
)

logger = logging.getLogger(__name__)


class SearchAndScrape:
    """
    Главный класс: выполняет поиск, скачивает контент из результатов,
    сохраняет в файл.
    """

    def __init__(
        self,
        provider: Optional[SearchProvider] = None,
        scraper: Optional[PageScraper] = None,
        num_results: int = 30,
    ):
        self.provider = provider or DuckDuckGoProvider()
        self.scraper = scraper or PageScraper()
        self.num_results = num_results

    def run(self, query: str) -> dict:
        """
        Выполнить полный цикл: поиск → скрапинг → возврат результатов.

        Returns:
            dict с ключами:
              - query: поисковый запрос
              - timestamp: время выполнения
              - total_results: количество найденных ссылок
              - scraped_ok: количество успешно скачанных страниц
              - scraped_fail: количество неудачных загрузок
              - results: список словарей с данными каждой страницы
        """
        logger.info("Searching for: '%s' (max %d results)", query, self.num_results)

        # 1. Поиск
        search_results = self.provider.search(query, self.num_results)
        urls = [r.url for r in search_results]

        logger.info("Found %d URLs, starting scraping...", len(urls))

        # 2. Скрапинг
        scraped_pages = self.scraper.scrape_urls(urls)

        # 3. Объединить результаты поиска и скрапинга
        url_to_search = {r.url: r for r in search_results}
        combined = []
        ok_count = 0
        fail_count = 0

        for page in scraped_pages:
            search_info = url_to_search.get(page.url)
            entry = {
                "url": page.url,
                "search_title": search_info.title if search_info else "",
                "search_snippet": search_info.snippet if search_info else "",
                "page_title": page.title,
                "text": page.text,
                "word_count": page.word_count,
                "success": page.success,
                "error": page.error,
            }
            combined.append(entry)
            if page.success:
                ok_count += 1
            else:
                fail_count += 1

        result = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "total_results": len(search_results),
            "scraped_ok": ok_count,
            "scraped_fail": fail_count,
            "results": combined,
        }

        logger.info(
            "Done: %d found, %d scraped OK, %d failed",
            len(search_results),
            ok_count,
            fail_count,
        )

        return result

    def run_and_save(self, query: str, output_path: Optional[str] = None) -> str:
        """
        Выполнить поиск+скрапинг и сохранить результаты в JSON-файл.

        Returns:
            Путь к сохранённому файлу.
        """
        result = self.run(query)

        if output_path is None:
            safe_query = "".join(c if c.isalnum() or c in " -_" else "" for c in query)
            safe_query = safe_query.strip().replace(" ", "_")[:50]
            output_path = f"search_results_{safe_query}.json"

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info("Results saved to %s", output_path)
        return output_path


def create_provider(
    provider_name: str = "duckduckgo",
    api_key: Optional[str] = None,
    cx: Optional[str] = None,
) -> SearchProvider:
    """
    Фабрика для создания провайдера поиска.

    Args:
        provider_name: "duckduckgo", "google_cse", или "serpapi"
        api_key: API-ключ (для google_cse и serpapi)
        cx: ID поисковой системы Google (только для google_cse)
    """
    name = provider_name.lower().strip()

    if name == "duckduckgo":
        return DuckDuckGoProvider()

    if name == "google_cse":
        key = api_key or os.environ.get("GOOGLE_API_KEY")
        cse_cx = cx or os.environ.get("GOOGLE_CSE_CX")
        if not key or not cse_cx:
            raise ValueError(
                "Google CSE requires api_key and cx. "
                "Set GOOGLE_API_KEY and GOOGLE_CSE_CX environment variables "
                "or pass them as arguments."
            )
        return GoogleCSEProvider(api_key=key, cx=cse_cx)

    if name == "serpapi":
        key = api_key or os.environ.get("SERPAPI_KEY")
        if not key:
            raise ValueError(
                "SerpAPI requires api_key. "
                "Set SERPAPI_KEY environment variable or pass it as argument."
            )
        return SerpAPIProvider(api_key=key)

    raise ValueError(f"Unknown provider: {provider_name}. Use: duckduckgo, google_cse, serpapi")
