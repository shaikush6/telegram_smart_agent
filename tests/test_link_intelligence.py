from types import SimpleNamespace

import pytest

import link_intelligence


@pytest.mark.asyncio
async def test_analyze_text_content_handles_missing_choices(monkeypatch):
    def fake_chat_completion(**kwargs):
        return SimpleNamespace(choices=None)

    monkeypatch.setattr(
        link_intelligence.client.chat.completions,
        "create",
        fake_chat_completion,
    )

    result = await link_intelligence.analyze_text_content("טקסט בעברית כלשהו")

    assert result["summary"] == "No summary available."
    assert result["categories"] == []
    assert result["entities"] == []
