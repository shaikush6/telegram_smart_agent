"""
link_processor.py - Utilities for fetching, parsing, and enriching link content.
"""

import base64
import logging
import math
import mimetypes
import re
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import requests
from bs4 import BeautifulSoup

from config import Config
from rendering_client import render_with_browser
from vision import extract_text_from_image

logger = logging.getLogger(__name__)

config = Config()
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0 Safari/537.36"
    ),
    "Accept-Language": "he,en-US,en;q=0.9,ar;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Charset": "utf-8, iso-8859-1;q=0.5",
}
SCREENSHOT_DIR = Path(config.SCREENSHOT_DIR)
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def fetch_page_content(url: str, *, timeout: int = 12) -> Optional[Dict[str, str]]:
    """
    Fetches the raw HTML for a URL with proper encoding detection.

    Returns:
        dict with keys: html, content_type, final_url
    """
    try:
        response = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Error fetching URL %s: %s", url, exc)
        return None

    content_type = response.headers.get("Content-Type", "")
    html = ""
    
    if "html" in content_type or "text" in content_type:
        # Improve encoding detection for international content (especially Hebrew)
        if response.encoding is None or response.encoding.lower() in ['iso-8859-1', 'ascii']:
            # If no encoding detected or default ISO encoding, try to detect from content
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for meta charset declaration
            charset_meta = soup.find('meta', attrs={'charset': True})
            if charset_meta and charset_meta.get('charset'):
                response.encoding = charset_meta['charset']
            else:
                # Look for http-equiv content-type
                content_type_meta = soup.find('meta', attrs={'http-equiv': re.compile(r'content-type', re.I)})
                if content_type_meta and content_type_meta.get('content'):
                    content = content_type_meta['content']
                    charset_match = re.search(r'charset=([^;\s]+)', content, re.I)
                    if charset_match:
                        response.encoding = charset_match.group(1)
                    else:
                        # Default to UTF-8 for better international support
                        response.encoding = 'utf-8'
                else:
                    # Default to UTF-8 for better international support  
                    response.encoding = 'utf-8'
        
        try:
            html = response.text
        except UnicodeDecodeError:
            # Fallback: try UTF-8 decoding directly
            try:
                html = response.content.decode('utf-8', errors='replace')
                logger.info("Used UTF-8 fallback decoding for %s", url)
            except Exception as decode_exc:
                logger.warning("Failed to decode content for %s: %s", url, decode_exc)
                html = response.content.decode('utf-8', errors='ignore')

    return {
        "html": html,
        "content_type": content_type,
        "final_url": response.url,
    }


def extract_text_content(html_content: str) -> str:
    """Converts HTML into a cleaned plain-text representation."""
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, "html.parser")
    for element in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        element.decompose()

    text = soup.get_text(separator=" ", strip=True)
    # Collapse extraneous whitespace so downstream NLP has cleaner input.
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _find_meta_content(soup: BeautifulSoup, names) -> Optional[str]:
    """Finds the first meta tag matching any of the provided names/properties."""
    for name in names:
        tag = soup.find("meta", attrs={"name": name}) or soup.find(
            "meta", attrs={"property": name}
        )
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def _absolute_url(href: Optional[str], base_url: Optional[str]) -> Optional[str]:
    if not href:
        return None
    if not base_url:
        return href
    return urljoin(base_url, href)


def extract_metadata(
    html_content: str,
    *,
    url: Optional[str] = None,
    content_type: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    """
    Extracts useful metadata from a page's HTML.
    """
    if not html_content:
        return {}

    soup = BeautifulSoup(html_content, "html.parser")

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    description = _find_meta_content(soup, ["og:description", "description"]) or ""
    author = _find_meta_content(
        soup,
        [
            "author",
            "article:author",
            "og:author",
            "twitter:creator",
        ],
    )
    publish_date = _find_meta_content(
        soup,
        [
            "article:published_time",
            "og:published_time",
            "publication_date",
            "date",
        ],
    )
    favicon_tag = soup.find("link", rel=lambda value: value and "icon" in value.lower())
    favicon = _absolute_url(favicon_tag["href"], url) if favicon_tag else None

    canonical_tag = soup.find("link", rel="canonical")
    canonical_href = canonical_tag["href"] if canonical_tag and canonical_tag.get("href") else None
    canonical_url = _absolute_url(canonical_href, url)

    html_tag = soup.find("html")
    language = html_tag.get("lang") if html_tag and html_tag.get("lang") else None

    text_content = extract_text_content(html_content)
    word_count = len(text_content.split())
    read_time = math.ceil(word_count / 200) if word_count else None

    domain = urlparse(url or "").netloc.lower() if url else None

    metadata = {
        "title": title or None,
        "description": description or None,
        "author": author,
        "publish_date": publish_date,
        "favicon": favicon,
        "domain": domain or None,
        "language": language.lower() if language else None,
        "content_type": content_type,
        "canonical_url": canonical_url or url,
        "word_count": word_count,
        "read_time": read_time,
        "text_content": text_content,
    }

    return metadata


def process_url(url: str) -> Optional[Dict[str, Optional[str]]]:
    """
    Convenience helper that fetches and parses all useful information for a link.
    Falls back to a headless browser render (and optionally OCR) when the direct fetch
    does not expose enough readable text.
    """
    page = fetch_page_content(url)
    if not page:
        return None

    final_url = page.get("final_url", url)
    metadata = extract_metadata(
        page["html"],
        url=final_url,
        content_type=page.get("content_type"),
    )

    text_content = metadata.pop("text_content", "") or ""
    extraction_method = "direct"
    render_status: Optional[str] = None
    screenshot_path: Optional[str] = None

    if _should_retry_with_renderer(text_content, metadata):
        render_result = render_with_browser(final_url)
        if render_result:
            extraction_method = "renderer"
            render_status = render_result.status
            final_url = render_result.resolved_url or final_url

            if render_result.html:
                page["html"] = render_result.html
                metadata = extract_metadata(
                    render_result.html,
                    url=final_url,
                    content_type=page.get("content_type"),
                )
                text_content = metadata.pop("text_content", "") or ""

            if not text_content and render_result.text_content:
                text_content = render_result.text_content.strip()

            if render_result.screenshot_base64:
                screenshot_path = _persist_screenshot(
                    render_result.screenshot_base64,
                    render_result.screenshot_mime or "image/png",
                )

                needs_ocr = not text_content or len(text_content.split()) < config.RENDERER_MIN_WORDS
                if needs_ocr:
                    ocr_text = extract_text_from_image(
                        render_result.screenshot_base64,
                        mime_type=render_result.screenshot_mime or "image/png",
                    )
                    if ocr_text:
                        text_content = ocr_text.strip()

    _update_metadata_counts(metadata, text_content)

    return {
        "html": page["html"],
        "resolved_url": final_url,
        "metadata": metadata,
        "text_content": text_content,
        "screenshot_path": screenshot_path,
        "extraction_method": extraction_method,
        "render_status": render_status,
    }


def _should_retry_with_renderer(text_content: str, metadata: Dict[str, Optional[str]]) -> bool:
    """Determines whether the renderer should be invoked for minimal pages."""
    if not config.ENABLE_RENDERER or not config.RENDERER_URL:
        return False

    if not text_content:
        return True

    word_count = len(text_content.split())
    if word_count >= config.RENDERER_MIN_WORDS:
        return False

    # When the page has only a short blurb and no description, attempt rendering.
    description = metadata.get("description") if metadata else None
    if word_count < config.RENDERER_MIN_WORDS and not description:
        return True

    return False


def _persist_screenshot(image_base64: str, mime_type: str) -> Optional[str]:
    """Stores the renderer-provided screenshot to disk and returns its path."""
    if not image_base64:
        return None

    try:
        image_bytes = base64.b64decode(image_base64)
    except (ValueError, TypeError) as exc:
        logger.warning("Failed to decode screenshot from renderer: %s", exc)
        return None

    extension = mimetypes.guess_extension(mime_type) or ".png"
    filename = f"rendered_{uuid4().hex}{extension}"
    path = SCREENSHOT_DIR / filename

    try:
        path.write_bytes(image_bytes)
        return str(path)
    except OSError as exc:
        logger.warning("Unable to persist screenshot %s: %s", filename, exc)
        return None


def _update_metadata_counts(metadata: Dict[str, Optional[str]], text_content: str) -> None:
    """Recalculates word count and read time based on the final text content."""
    word_count = len(text_content.split())
    read_time = math.ceil(word_count / 200) if word_count else None
    metadata["word_count"] = word_count
    metadata["read_time"] = read_time


if __name__ == "__main__":
    # Simple manual test for development
    test_url = "https://www.example.com"
    result = process_url(test_url)
    if result:
        print(f"Resolved URL: {result['resolved_url']}")
        print(f"Title: {result['metadata'].get('title')}")
        print(f"Description: {result['metadata'].get('description')}")
        print(f"Word count: {result['metadata'].get('word_count')}")
        print(f"Read time: {result['metadata'].get('read_time')} min")
