from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import link_retriever


@pytest.fixture(autouse=True)
def reset_database(monkeypatch):
    """Provide no-op defaults for database helpers between tests."""
    monkeypatch.setattr(
        link_retriever,
        "database",
        SimpleNamespace(
            get_recent_links=lambda user_id, limit=5: [],
            search_links=lambda user_id, query, limit=10: [],
        ),
    )


def test_recent_keyword_shortcuts_to_recent_links(monkeypatch):
    expected = [{"title": "Most recent"}]
    monkeypatch.setattr(
        link_retriever.database,
        "get_recent_links",
        lambda user_id, limit=5: expected,
    )

    results = link_retriever.find_links_by_query(123, "show me my recent links", limit=5)
    assert results == expected


def test_time_window_filters_results(monkeypatch):
    now = datetime.now(timezone.utc)
    older = now - timedelta(days=10)
    recent = now - timedelta(days=2)

    sample_results = [
        {"created_at": recent, "title": "Recent link"},
        {"created_at": older, "title": "Old link"},
    ]

    monkeypatch.setattr(
        link_retriever.database,
        "search_links",
        lambda user_id, query, limit=10: sample_results,
    )

    results = link_retriever.find_links_by_query(1, "something last week", limit=5)
    assert len(results) == 1
    assert results[0]["title"] == "Recent link"


def test_fallback_to_raw_query_when_initial_cleaned_search_empty(monkeypatch):
    calls = []

    def fake_search(user_id, query, limit=10):
        calls.append(query)
        if query.strip() == "docs":
            return []
        return [{"title": "Match"}]

    monkeypatch.setattr(link_retriever.database, "search_links", fake_search)

    results = link_retriever.find_links_by_query(4, "show me docs", limit=5)
    assert results[0]["title"] == "Match"
    # Two calls: first with cleaned terms, second with raw query.
    assert calls[0] == "docs"
    assert calls[1] == "show me docs"
