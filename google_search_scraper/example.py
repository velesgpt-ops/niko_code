"""
Примеры использования модуля google_search_scraper.
"""

from google_search_scraper import SearchAndScrape, DuckDuckGoProvider, PageScraper
from google_search_scraper.core import create_provider


def example_basic():
    """Базовый пример — поиск через DuckDuckGo (без API-ключа)."""
    engine = SearchAndScrape(num_results=10)
    result = engine.run("Python web scraping tutorial")

    print(f"Найдено: {result['total_results']} ссылок")
    print(f"Успешно скачано: {result['scraped_ok']}")
    print(f"Ошибки: {result['scraped_fail']}")

    for r in result["results"][:3]:
        print(f"\n--- {r['url']} ---")
        print(f"Title: {r['page_title']}")
        print(f"Words: {r['word_count']}")
        print(f"Text preview: {r['text'][:200]}...")


def example_save_to_file():
    """Поиск и сохранение в JSON-файл."""
    engine = SearchAndScrape(num_results=30)
    path = engine.run_and_save("machine learning basics")
    print(f"Результаты сохранены в: {path}")


def example_google_cse():
    """Поиск через Google Custom Search API (нужны API-ключи)."""
    # Установите переменные окружения:
    #   export GOOGLE_API_KEY="your-key"
    #   export GOOGLE_CSE_CX="your-cx-id"
    provider = create_provider("google_cse")
    engine = SearchAndScrape(provider=provider, num_results=30)
    result = engine.run("artificial intelligence")
    print(f"Найдено: {result['total_results']}")


def example_custom_scraper():
    """Пример с настроенным скрапером (больше потоков, увеличенный таймаут)."""
    scraper = PageScraper(
        timeout=20,
        max_workers=10,
        max_text_length=100000,
    )
    engine = SearchAndScrape(scraper=scraper, num_results=30)
    result = engine.run("data science tools 2024")

    total_words = sum(r["word_count"] for r in result["results"])
    print(f"Всего слов скачано: {total_words}")


if __name__ == "__main__":
    example_basic()
