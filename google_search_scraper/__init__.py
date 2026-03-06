"""
Google Search Scraper — модуль для поиска в Google и скачивания контента
из результатов поиска.

Поддерживаемые бэкенды поиска:
- DuckDuckGo (бесплатно, без API-ключа)
- Google Custom Search API (нужен API-ключ)
- SerpAPI (нужен API-ключ)
"""

from google_search_scraper.search_providers import (
    DuckDuckGoProvider,
    GoogleCSEProvider,
    SerpAPIProvider,
)
from google_search_scraper.scraper import PageScraper
from google_search_scraper.core import SearchAndScrape

__all__ = [
    "DuckDuckGoProvider",
    "GoogleCSEProvider",
    "SerpAPIProvider",
    "PageScraper",
    "SearchAndScrape",
]
