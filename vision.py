"""
vision.py - Utilities for extracting text from screenshots using OpenAI vision models.
"""

import logging
from typing import Dict, List

from openai import OpenAI

from config import Config

logger = logging.getLogger(__name__)

config = Config()
client = OpenAI(api_key=config.OPENAI_API_KEY)


def _collect_output_text(output: List[Dict]) -> str:
    """Extracts concatenated text from the responses API output structure."""
    chunks: List[str] = []
    for item in output or []:
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                chunks.append(content["text"])
    return "\n".join(chunk.strip() for chunk in chunks if chunk).strip()


def extract_text_from_image(image_base64: str, *, mime_type: str = "image/png") -> str:
    """
    Uses an OpenAI vision-capable model to transcribe text from a screenshot.
    Returns an empty string when vision processing is disabled or fails.
    """
    if not config.ENABLE_SCREENSHOT_OCR or not image_base64:
        return ""

    try:
        response = client.responses.create(
            model=config.VISION_MODEL,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Extract all visible text from this screenshot. "
                                "Return plain text only without additional commentary."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_base64": image_base64,
                            "mime_type": mime_type,
                        },
                    ],
                }
            ],
        )

        if hasattr(response, "model_dump"):
            payload = response.model_dump()
        elif hasattr(response, "to_dict"):
            payload = response.to_dict()
        else:
            payload = getattr(response, "__dict__", {})

        text_output = _collect_output_text(payload.get("output", []))
        if text_output:
            return text_output

        # Some responses return content at the top-level "content" field.
        return _collect_output_text(payload.get("content", []))
    except Exception as exc:  # noqa: broad-except -- avoid breaking ingestion pipeline.
        logger.warning("Vision OCR failed: %s", exc)
        return ""
