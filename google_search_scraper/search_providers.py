"""
Провайдеры поиска — альтернативные способы получить результаты поиска Google.
"""

import logging
import math
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Один результат поиска."""

    title: str
    url: str
    snippet: str = ""


class SearchProvider(ABC):
    """Базовый класс для провайдеров поиска."""

    @abstractmethod
    def search(self, query: str, num_results: int = 30) -> list[SearchResult]:
        """Выполнить поиск и вернуть список результатов."""
        ...


class DuckDuckGoProvider(SearchProvider):
    """
    Поиск через DuckDuckGo.
    Бесплатный, не требует API-ключа.
    Результаты по релевантности близки к Google.
    """

    def search(self, query: str, num_results: int = 30) -> list[SearchResult]:
        from ddgs import DDGS

        results = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=num_results):
                    results.append(
                        SearchResult(
                            title=r.get("title", ""),
                            url=r.get("href", ""),
                            snippet=r.get("body", ""),
                        )
                    )
        except Exception as e:
            logger.error("DuckDuckGo search failed: %s", e)
            raise

        logger.info("DuckDuckGo: found %d results for '%s'", len(results), query)
        return results


class GoogleCSEProvider(SearchProvider):
    """
    Поиск через Google Custom Search Engine (официальный API).
    Требует API-ключ и ID поисковой системы (cx).
    Бесплатный лимит: 100 запросов в день.

    Получить ключи:
    1. https://console.cloud.google.com/ → API & Services → Credentials → Create API Key
    2. https://programmablesearchengine.google.com/ → создать поисковик → взять cx
    """

    API_URL = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, api_key: str, cx: str):
        self.api_key = api_key
        self.cx = cx

    def search(self, query: str, num_results: int = 30) -> list[SearchResult]:
        results = []
        # Google CSE API возвращает max 10 результатов за запрос
        pages_needed = math.ceil(num_results / 10)

        for page in range(pages_needed):
            start_index = page * 10 + 1
            params = {
                "key": self.api_key,
                "cx": self.cx,
                "q": query,
                "start": start_index,
                "num": min(10, num_results - len(results)),
            }

            try:
                resp = requests.get(self.API_URL, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as e:
                logger.error("Google CSE request failed (page %d): %s", page, e)
                break

            items = data.get("items", [])
            if not items:
                break

            for item in items:
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                    )
                )

            if len(results) >= num_results:
                break

            # Пауза между запросами, чтобы не превысить rate limit
            time.sleep(0.5)

        logger.info("Google CSE: found %d results for '%s'", len(results), query)
        return results[:num_results]


class SerpAPIProvider(SearchProvider):
    """
    Поиск через SerpAPI — сервис-посредник для Google.
    Требует API-ключ (https://serpapi.com/).
    Бесплатный план: 100 запросов/месяц.
    """

    API_URL = "https://serpapi.com/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, num_results: int = 30) -> list[SearchResult]:
        results = []
        start = 0

        while len(results) < num_results:
            params = {
                "api_key": self.api_key,
                "engine": "google",
                "q": query,
                "start": start,
                "num": min(10, num_results - len(results)),
            }

            try:
                resp = requests.get(self.API_URL, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as e:
                logger.error("SerpAPI request failed (start=%d): %s", start, e)
                break

            organic = data.get("organic_results", [])
            if not organic:
                break

            for item in organic:
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("link", ""),
                        snippet=item.get("snippet", ""),
                    )
                )

            start += 10
            time.sleep(0.3)

        logger.info("SerpAPI: found %d results for '%s'", len(results), query)
        return results[:num_results]
