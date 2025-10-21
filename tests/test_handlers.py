from html import unescape
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import handlers


class FakeMessage:
    def __init__(self):
        self.sent_messages = []

    async def reply_text(self, text, parse_mode=None, disable_web_page_preview=None):
        self.sent_messages.append(
            {
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_web_page_preview,
            }
        )


class FakeUpdate:
    def __init__(self, message_text: str):
        self.message = FakeMessage()
        self.message.text = message_text


@pytest.mark.asyncio
async def test_handle_urls_persists_data_and_replies(monkeypatch):
    # Stub database functions to track calls without touching Postgres.
    db_calls = {
        "add_link": [],
        "update_link_details": [],
        "add_link_metadata": [],
        "add_link_categories": [],
        "add_link_entities": [],
        "record_link_source": [],
        "store_link_embedding": [],
    }

    monkeypatch.setattr(
        handlers.database,
        "add_user",
        lambda user_id, username: None,
    )
    monkeypatch.setattr(
        handlers.database,
        "add_link",
        lambda *args, **kwargs: db_calls["add_link"].append((args, kwargs)) or 101,
    )
    monkeypatch.setattr(
        handlers.database,
        "update_link_details",
        lambda *args, **kwargs: db_calls["update_link_details"].append((args, kwargs)),
    )
    monkeypatch.setattr(
        handlers.database,
        "add_link_metadata",
        lambda *args, **kwargs: db_calls["add_link_metadata"].append((args, kwargs)),
    )
    monkeypatch.setattr(
        handlers.database,
        "add_link_categories",
        lambda *args, **kwargs: db_calls["add_link_categories"].append((args, kwargs)),
    )
    monkeypatch.setattr(
        handlers.database,
        "add_link_entities",
        lambda *args, **kwargs: db_calls["add_link_entities"].append((args, kwargs)),
    )
    monkeypatch.setattr(
        handlers.database,
        "record_link_source",
        lambda *args, **kwargs: db_calls["record_link_source"].append((args, kwargs)),
    )
    monkeypatch.setattr(
        handlers.database,
        "store_link_embedding",
        lambda *args, **kwargs: db_calls["store_link_embedding"].append((args, kwargs)),
    )

    fake_page = {
        "resolved_url": "https://example.com/article",
        "metadata": {
            "title": "Example Title",
            "description": "Example description",
            "domain": "example.com",
        },
        "text_content": "This is example content.",
        "html": "<html></html>",
    }

    monkeypatch.setattr(handlers, "process_url", lambda url: fake_page)

    fake_analysis = {
        "summary": "AI summary.",
        "categories": ["article", "ai"],
        "entities": [{"name": "Example Corp", "type": "company"}],
    }
    monkeypatch.setattr(
        handlers,
        "analyze_text_content",
        AsyncMock(return_value=fake_analysis),
    )
    monkeypatch.setattr(
        handlers,
        "generate_embedding",
        AsyncMock(return_value={"vector": [0.1, 0.2, 0.3], "model": "test-emb"}),
    )

    update = SimpleNamespace(message=FakeMessage())
    update.message.text = "Check this out: https://example.com/article"

    await handlers.handle_urls(update, user_id=42, urls=["https://example.com/article"])

    # Database calls were recorded
    assert db_calls["add_link"]
    assert db_calls["update_link_details"]
    assert db_calls["add_link_metadata"]
    assert db_calls["add_link_categories"]
    assert db_calls["add_link_entities"]
    assert db_calls["record_link_source"]
    assert db_calls["store_link_embedding"]

    # User gets a formatted response with the title and summary.
    sent = update.message.sent_messages[0]
    assert "Example Title" in sent["text"]
    assert "AI summary" in sent["text"]
    assert sent["parse_mode"] == "HTML"
    assert sent["disable_web_page_preview"] is True


@pytest.mark.asyncio
async def test_handle_urls_handles_pages_without_text(monkeypatch):
    db_calls = {
        "add_link": [],
        "update_link_details": [],
        "add_link_metadata": [],
        "add_link_categories": [],
        "add_link_entities": [],
        "record_link_source": [],
        "store_link_embedding": [],
    }

    monkeypatch.setattr(handlers.database, "add_user", lambda user_id, username: None)
    monkeypatch.setattr(
        handlers.database,
        "add_link",
        lambda *args, **kwargs: db_calls["add_link"].append((args, kwargs)) or 303,
    )
    monkeypatch.setattr(
        handlers.database,
        "update_link_details",
        lambda *args, **kwargs: db_calls["update_link_details"].append((args, kwargs)),
    )
    monkeypatch.setattr(
        handlers.database,
        "add_link_metadata",
        lambda *args, **kwargs: db_calls["add_link_metadata"].append((args, kwargs)),
    )
    monkeypatch.setattr(
        handlers.database,
        "add_link_categories",
        lambda *args, **kwargs: db_calls["add_link_categories"].append((args, kwargs)),
    )
    monkeypatch.setattr(
        handlers.database,
        "add_link_entities",
        lambda *args, **kwargs: db_calls["add_link_entities"].append((args, kwargs)),
    )
    monkeypatch.setattr(
        handlers.database,
        "record_link_source",
        lambda *args, **kwargs: db_calls["record_link_source"].append((args, kwargs)),
    )
    monkeypatch.setattr(
        handlers.database,
        "store_link_embedding",
        lambda *args, **kwargs: db_calls["store_link_embedding"].append((args, kwargs)),
    )

    monkeypatch.setattr(
        handlers,
        "process_url",
        lambda url: {
            "resolved_url": url,
            "metadata": {"title": "Private Invoice", "description": None, "domain": "mrng.to"},
            "text_content": "",
            "html": "<html></html>",
        },
    )
    monkeypatch.setattr(
        handlers,
        "analyze_text_content",
        AsyncMock(return_value={"summary": "", "categories": [], "entities": []}),
    )
    monkeypatch.setattr(handlers, "generate_embedding", AsyncMock(return_value=None))

    update = SimpleNamespace(message=FakeMessage())
    update.message.text = "Please store this: https://example.com/secure"

    await handlers.handle_urls(update, user_id=7, urls=["https://example.com/secure"])

    assert not db_calls["add_link_categories"]
    assert not db_calls["add_link_entities"]
    assert not db_calls["store_link_embedding"]

    sent = update.message.sent_messages[0]
    rendered_text = unescape(sent["text"])
    assert "Private Invoice" in rendered_text
    assert "I couldn't read the page contents" in rendered_text
