# Testing Plan

This document outlines how to validate the refactored Silo bot. It covers testing goals, suggested tooling, scenarios, and data seeding strategies.

## Tooling
- **Test runner**: `pytest`
- **Async support**: `pytest-asyncio` for `async def` handlers
- **Database fixtures**: `pytest-postgresql` or custom fixtures that spin up a temporary Postgres schema per test
- **HTTP mocking**: `responses` or `pytest-httpx` to stub outbound requests from `requests`
- **OpenAI mocking**: monkeypatch `link_intelligence.client` methods to return deterministic payloads

## Unit Tests
| Area | What to Cover | Notes |
|------|---------------|-------|
| `link_processor.extract_metadata` | Title detection, meta tags precedence, canonical URL, read-time calculation | Use static HTML fixtures |
| `link_processor.extract_text_content` | Strips scripts/styles, collapses whitespace | |
| `link_retriever.find_links_by_query` | Temporal windows, stop-word removal, entity extraction, fallback behaviour | Mock `database.search_links` and `get_recent_links` |
| `database._parse_datetime` | ISO, ISOZ, blanks | Pure function ->
| `database.add_link_categories` / `add_link_entities` | Deduplication, empty input no-op | Use `pytest` monkeypatch to assert executed SQL |
| `link_intelligence._normalise_ai_output` | Handles malformed payloads, duplicates categories | Provide mocked AI responses |

## Integration Tests
1. **Schema bootstrap**
   - Run `database.create_tables(reset=True)` against a temp DB.
   - Assert that all expected tables exist (links, metadata, categories, entities, snapshots, embeddings).
2. **URL ingestion happy path**
   - Mock `process_url` to return deterministic metadata/text.
   - Mock OpenAI chat + embeddings calls to return known values.
   - Feed a fake Telegram `Update` with a URL into `handlers.handle_message`.
   - Assert:
     - Row created in `links` with title/summary.
     - Metadata, categories, entities populated.
     - Embedding stored with the chosen model name.
     - Bot reply text includes the summary and clean HTML.
3. **Natural-language search**
   - Seed the DB with a few links, metadata, entities.
   - Call `handlers.search_command` and ensure the reply contains the correct ranking and HTML formatting.
4. **Export command**
   - Seed multiple links.
  - Invoke `handlers.export_command` and intercept `context.bot.send_document`; verify CSV headers and row counts.
5. **Archive command**
   - Monkeypatch `link_archiver.archive_link` to return a fake path.
   - Ensure handler response includes the path and that `link_snapshots` receives a record.

## Test Data & Fixtures
- Place HTML samples under `tests/fixtures/html/`.
- Provide JSON fixtures for AI responses (summary + embedding).
- For Telegram, build minimal `Update` objects using `telegram.Update.de_json()` with sample payloads.

## Execution
- Run all tests:
  ```bash
  pytest
  ```
- To focus on async handlers:
  ```bash
  pytest tests/test_handlers.py -k "async"
  ```

## Continuous Integration
- Add a GitHub Actions (or similar) workflow that:
  1. Sets up Python and installs dependencies.
  2. Spins up Postgres (services: postgres).
  3. Runs `pytest`.
  4. Optionally runs `ruff` or `flake8` for linting.

## Future Enhancements
- Snapshot tests for rendered HTML responses using `pytest-regressions`.
- Load tests on embedding generation using a queue and worker pool.
- Contract tests for external APIs (Wayback, Browserless) once integrated, guarding against breaking changes.
