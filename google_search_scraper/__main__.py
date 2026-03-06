"""
CLI-интерфейс для модуля google_search_scraper.

Примеры использования:
    python -m google_search_scraper "Python web scraping tutorial"
    python -m google_search_scraper "machine learning" --num 20 --provider duckduckgo
    python -m google_search_scraper "AI news" --output results.json --provider google_cse
"""

import argparse
import logging
import sys

from google_search_scraper.core import SearchAndScrape, create_provider
from google_search_scraper.scraper import PageScraper


def main():
    parser = argparse.ArgumentParser(
        description="Поиск в Google и скачивание контента из результатов поиска.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s "Python tutorial"
  %(prog)s "machine learning" --num 20 --provider duckduckgo
  %(prog)s "AI news" --output results.json --provider google_cse
  %(prog)s "web scraping" --workers 10 --timeout 20

Провайдеры поиска:
  duckduckgo  — бесплатный, без API-ключа (по умолчанию)
  google_cse  — Google Custom Search API (нужны GOOGLE_API_KEY, GOOGLE_CSE_CX)
  serpapi      — SerpAPI (нужен SERPAPI_KEY)
        """,
    )
    parser.add_argument("query", help="Поисковый запрос")
    parser.add_argument(
        "-n", "--num", type=int, default=30, help="Количество результатов (по умолчанию: 30)"
    )
    parser.add_argument(
        "-p",
        "--provider",
        default="duckduckgo",
        choices=["duckduckgo", "google_cse", "serpapi"],
        help="Провайдер поиска (по умолчанию: duckduckgo)",
    )
    parser.add_argument("-o", "--output", help="Путь для сохранения JSON-файла с результатами")
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=5,
        help="Количество потоков для скачивания (по умолчанию: 5)",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=15,
        help="Таймаут для HTTP-запросов в секундах (по умолчанию: 15)",
    )
    parser.add_argument(
        "--api-key", help="API-ключ (для google_cse или serpapi)"
    )
    parser.add_argument(
        "--cx", help="Google CSE ID (для google_cse)"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Подробный вывод (DEBUG)"
    )

    args = parser.parse_args()

    # Настройка логирования
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        provider = create_provider(args.provider, api_key=args.api_key, cx=args.cx)
    except ValueError as e:
        print(f"Ошибка конфигурации: {e}", file=sys.stderr)
        sys.exit(1)

    scraper = PageScraper(timeout=args.timeout, max_workers=args.workers)
    engine = SearchAndScrape(provider=provider, scraper=scraper, num_results=args.num)

    print(f"Поиск: '{args.query}' (провайдер: {args.provider}, результатов: {args.num})")
    print("=" * 60)

    output_path = engine.run_and_save(args.query, output_path=args.output)

    print("=" * 60)
    print(f"Результаты сохранены в: {output_path}")


if __name__ == "__main__":
    main()
