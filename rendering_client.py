"""
rendering_client.py - Calls an external headless browser service to render pages.

The service is expected to expose a simple HTTP API:

POST /render { "url": "<page url>" }

Response (JSON):
{
    "html": "<rendered html>",
    "text_content": "<plain text>",
    "resolved_url": "<final url after redirects>",
    "screenshot_base64": "<optional base64 encoded image>",
    "screenshot_mime": "image/png"
}
"""

from dataclasses import dataclass
import logging
from typing import Optional
import requests

from config import Config

logger = logging.getLogger(__name__)
config = Config()


@dataclass
class RenderResult:
    html: str = ""
    text_content: str = ""
    resolved_url: Optional[str] = None
    screenshot_base64: Optional[str] = None
    screenshot_mime: Optional[str] = None
    status: Optional[str] = None


def render_with_browser(url: str) -> Optional[RenderResult]:
    """
    Calls the configured renderer service to obtain a fully rendered DOM (with JS executed).
    Returns a RenderResult on success or None when rendering should be considered unavailable.
    """
    if not config.ENABLE_RENDERER or not config.RENDERER_URL:
        logger.debug("Renderer disabled or not configured; skipping render for %s", url)
        return None

    payload = {"url": url}
    headers = {"Accept": "application/json"}
    if config.RENDERER_API_KEY:
        headers["Authorization"] = f"Bearer {config.RENDERER_API_KEY}"

    try:
        response = requests.post(
            config.RENDERER_URL,
            json=payload,
            headers=headers,
            timeout=config.RENDERER_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Renderer request failed for %s: %s", url, exc)
        return None

    try:
        data = response.json()
    except ValueError:
        logger.warning("Renderer returned non-JSON payload for %s", url)
        return None

    html = data.get("html") or ""
    text_content = data.get("text_content") or ""
    resolved_url = data.get("resolved_url")
    screenshot_base64 = data.get("screenshot_base64")
    screenshot_mime = data.get("screenshot_mime") or "image/png"
    status = data.get("status")

    if not (html or text_content or screenshot_base64):
        logger.info("Renderer returned empty content for %s", url)
        return None

    return RenderResult(
        html=html,
        text_content=text_content,
        resolved_url=resolved_url,
        screenshot_base64=screenshot_base64,
        screenshot_mime=screenshot_mime,
        status=status,
    )
