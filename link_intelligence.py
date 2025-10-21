"""
link_intelligence.py - AI-powered link understanding utilities.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI

from config import Config
from link_processor import process_url

logger = logging.getLogger(__name__)

config = Config()
client = OpenAI(api_key=config.OPENAI_API_KEY)

DEFAULT_MODEL = config.DEFAULT_MODEL or "gpt-4o-mini"
DEFAULT_EMBEDDING_MODEL = config.EMBEDDING_MODEL or "text-embedding-3-small"
DEFAULT_ANALYSIS = {
    "category": None,
    "categories": [],
    "topics": [],
    "entities": [],
    "summary": "No summary available.",
    "tags": [],
}


async def process_link(url: str) -> Dict[str, Any]:
    """
    Fetches, parses, and enriches a link with AI metadata.
    """
    page = process_url(url)
    if not page:
        return {"error": "Failed to fetch URL content."}

    ai_analysis = await analyze_text_content(page["text_content"])

    return {
        "resolved_url": page["resolved_url"],
        "metadata": page["metadata"],
        "analysis": ai_analysis,
        "text_content": page["text_content"],
        "html": page["html"],
    }


async def analyze_text_content(text_content: str, *, model: Optional[str] = None, user_context: Optional[str] = None) -> Dict[str, Any]:
    """
    Uses OpenAI to analyse the text content of a link and return structured information.
    """
    if not text_content:
        logger.info("Skipping AI analysis because no textual content was extracted.")
        return DEFAULT_ANALYSIS.copy()

    system_prompt = (
        "You are an expert content analyst assisting a knowledge management bot. "
        "Your job is to analyze web content and extract rich, searchable metadata. "
        "Given cleaned text from a webpage (and optional user context), respond with a JSON object containing:\n"
        '- type: Primary content type (article, video, form, document, product, tutorial, session, conversation, tool, other).\n'
        "- topics: 5-8 comprehensive key topics, including technical concepts, tools, and domains mentioned.\n"
        "- entities: Key people, organizations, products, tools, technologies as objects with `name` and `type` (person/org/product/tool/tech).\n"
        "- summary: 2-3 sentence human-friendly summary that captures the main value and purpose.\n"
        "- tags: Rich set of searchable keywords including synonyms, technical terms, and user intent keywords.\n"
        "- context_keywords: If user context provided, extract additional relevant search terms from user's description.\n"
        "- emotional_tags: Sentiment/importance indicators from user context (important, useful, reference, example, etc).\n"
        "\nFocus on making content highly discoverable through natural language search."
    )

    # Construct user message with content and optional context
    user_message_parts = []
    if user_context:
        user_message_parts.append(f"USER CONTEXT: {user_context}")
        user_message_parts.append("---")
    user_message_parts.append(f"WEBPAGE CONTENT: {text_content[:6000]}")
    
    user_message = "\n".join(user_message_parts)
    
    model_to_use = model or DEFAULT_MODEL
    payload = {
        "model": model_to_use,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 800,  # Increased for richer analysis
        "temperature": 0.3,  # Slightly lower for more consistent extraction
        "response_format": {"type": "json_object"},
    }

    loop = asyncio.get_running_loop()
    try:
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(**payload),
        )
        if not response or not getattr(response, "choices", None):
            logger.warning("AI analysis returned no choices for supplied content.")
            return DEFAULT_ANALYSIS.copy()

        first_choice = response.choices[0] if response.choices else None
        message = getattr(first_choice, "message", None) if first_choice else None
        ai_payload = getattr(message, "content", None) if message else None
        if not ai_payload:
            logger.warning("AI analysis returned an empty message payload.")
            return DEFAULT_ANALYSIS.copy()

        parsed = json.loads(ai_payload) if ai_payload else {}
    except Exception as exc:  # noqa: broad-except - downstream consumers need a graceful fallback
        logger.warning("AI analysis error: %s", exc)
        if not model and model_to_use != "gpt-4o-mini":
            # Retry once with a lightweight default model before giving up.
            return await analyze_text_content(text_content, model="gpt-4o-mini")
        return DEFAULT_ANALYSIS.copy()

    return _normalise_ai_output(parsed)


async def generate_embedding(text_content: str, *, model: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Generates an embedding for the supplied content using OpenAI embeddings API.
    Returns a dict with keys `vector` and `model`.
    """
    if not text_content:
        return None

    model_to_use = model or DEFAULT_EMBEDDING_MODEL
    payload = {
        "model": model_to_use,
        "input": text_content,
    }

    loop = asyncio.get_running_loop()
    try:
        response = await loop.run_in_executor(
            None,
            lambda: client.embeddings.create(**payload),
        )
        vector = response.data[0].embedding if response and response.data else None
        if not vector:
            return None
        return {"vector": vector, "model": model_to_use}
    except Exception as exc:  # noqa: broad-except -- we surface failure but keep pipeline alive.
        logger.warning("Embedding generation error: %s", exc)
        return None


def _normalise_ai_output(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalises the OpenAI response into the structure expected by downstream consumers."""
    if not isinstance(raw, dict):
        return DEFAULT_ANALYSIS.copy()

    category = raw.get("type") or raw.get("category")
    topics = _ensure_list_of_strings(raw.get("topics"))
    tags = _ensure_list_of_strings(raw.get("tags"))

    entities_input = raw.get("entities") or []
    entities: List[Dict[str, Optional[str]]] = []
    if isinstance(entities_input, list):
        for item in entities_input:
            if isinstance(item, dict):
                name = item.get("name") or item.get("entity") or item.get("value")
                entity_type = item.get("type") or item.get("category")
            else:
                name = str(item)
                entity_type = None
            if not name:
                continue
            entities.append({"name": name, "type": entity_type})

    categories: List[str] = []
    if category:
        categories.append(str(category))
    categories.extend(topic for topic in topics if topic)

    summary = raw.get("summary") or DEFAULT_ANALYSIS["summary"]

    return {
        "category": category,
        "categories": list(dict.fromkeys(categories)),  # preserve order, remove duplicates
        "topics": topics,
        "entities": entities,
        "summary": summary,
        "tags": tags,
    }


def _ensure_list_of_strings(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


if __name__ == "__main__":
    async def _demo():
        url = "https://openai.com/research/gpt-4"
        enriched = await process_link(url)
        print(json.dumps(enriched, indent=2, default=str))

    asyncio.run(_demo())
