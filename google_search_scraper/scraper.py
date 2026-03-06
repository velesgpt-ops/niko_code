"""
Скрапер контента веб-страниц.
Скачивает HTML, извлекает текст, сохраняет результаты.
"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# User-Agent, имитирующий обычный браузер
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Теги, из которых мы извлекаем текст
CONTENT_TAGS = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "td", "th", "blockquote", "pre"]

# Теги, которые удаляем перед извлечением (навигация, реклама, скрипты)
REMOVE_TAGS = ["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]


@dataclass
class ScrapedPage:
    """Результат скрапинга одной страницы."""

    url: str
    title: str = ""
    text: str = ""
    success: bool = True
    error: str = ""
    word_count: int = 0


class PageScraper:
    """Скрапер для загрузки и извлечения текста из веб-страниц."""

    def __init__(
        self,
        timeout: int = 15,
        max_workers: int = 5,
        user_agent: str = DEFAULT_USER_AGENT,
        max_text_length: int = 50000,
    ):
        self.timeout = timeout
        self.max_workers = max_workers
        self.max_text_length = max_text_length
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }
        )

    def scrape_url(self, url: str) -> ScrapedPage:
        """Скачать и извлечь текст из одной страницы."""
        try:
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return ScrapedPage(
                    url=url,
                    success=False,
                    error=f"Not HTML: {content_type}",
                )

            resp.encoding = resp.apparent_encoding or "utf-8"
            html = resp.text

            title, text = self._extract_content(html)
            text = text[: self.max_text_length]
            word_count = len(text.split())

            logger.info("Scraped %s — %d words", url, word_count)
            return ScrapedPage(
                url=url,
                title=title,
                text=text,
                word_count=word_count,
            )

        except requests.Timeout:
            logger.warning("Timeout: %s", url)
            return ScrapedPage(url=url, success=False, error="Timeout")
        except requests.RequestException as e:
            logger.warning("Request error for %s: %s", url, e)
            return ScrapedPage(url=url, success=False, error=str(e))
        except Exception as e:
            logger.warning("Unexpected error for %s: %s", url, e)
            return ScrapedPage(url=url, success=False, error=str(e))

    def scrape_urls(self, urls: list[str]) -> list[ScrapedPage]:
        """Скачать контент из списка URL параллельно."""
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {executor.submit(self.scrape_url, url): url for url in urls}
            for future in as_completed(future_to_url):
                results.append(future.result())

        # Сохранить порядок как в исходном списке URL
        url_order = {url: i for i, url in enumerate(urls)}
        results.sort(key=lambda r: url_order.get(r.url, len(urls)))

        return results

    def _extract_content(self, html: str) -> tuple[str, str]:
        """Извлечь заголовок и основной текст из HTML."""
        soup = BeautifulSoup(html, "html.parser")

        # Получить title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Удалить ненужные теги
        for tag_name in REMOVE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Попробовать найти основной контент
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", {"role": "main"})
            or soup.find("div", class_=re.compile(r"content|article|post|entry", re.I))
        )

        target = main_content if main_content else soup.body if soup.body else soup

        # Извлечь текст из контентных тегов
        paragraphs = []
        for tag in target.find_all(CONTENT_TAGS):
            text = tag.get_text(separator=" ", strip=True)
            if text and len(text) > 20:
                paragraphs.append(text)

        # Если мало текста из тегов, взять весь текст
        if len(paragraphs) < 3:
            full_text = target.get_text(separator="\n", strip=True)
            # Убрать множественные пробелы и пустые строки
            lines = [line.strip() for line in full_text.splitlines() if line.strip()]
            text = "\n".join(lines)
        else:
            text = "\n\n".join(paragraphs)

        return title, text
