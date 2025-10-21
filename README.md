# Silo – Telegram Link Intelligence Bot

Silo transforms the old ShopSmart shopping assistant into an intelligent link manager. Drop any URL or natural-language request into Telegram and the bot ingests the page, analyses it with OpenAI, classifies and tags it, and makes it searchable later.

## Quick Start

1. **Create and activate a virtualenv**
   ```bash
   cd telegram_smart_agent
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Configure your environment**
   - Copy `.env.example` to `.env`
   - Fill in the values:
     ```
     TELEGRAM_TOKEN=your_bot_token
     OPENAI_API_KEY=sk-your-key
     DEFAULT_MODEL=gpt-4o-mini
     EMBEDDING_MODEL=text-embedding-3-small
     ```
   - Update the database fields if you deploy against a remote Postgres instance.
3. **Bootstrap the schema once**
   ```bash
   python3 -c "import database; database.create_tables()"
   ```
4. **Run the bot**
   ```bash
   python3 main_bot.py
   ```

Stop the bot with `Ctrl+C`. Logs are streamed to stdout by default.

## Core Capabilities

- **Link ingestion** – Detect URLs in any message, resolve redirects, and capture metadata (title, description, author, publish date, favicon, language, word count).
- **AI enrichment** – Use OpenAI chat models to classify content type, derive topics, extract named entities, and create human summaries.
- **Embeddings ready** – Generate OpenAI embeddings (`text-embedding-3-small` by default) and store them for future semantic search upgrades.
- **Command surface** – `/recent`, `/search`, `/stats`, `/export`, `/archive`, `/help`.
- **Natural-language search** – Lightweight NLP parses temporal hints (“last week”), entity clues (“from Sarah”), and falls back to Postgres full-text search.
- **Archiving** – Ask the Wayback Machine to archive each link and fall back to a local HTML copy if the remote snapshot fails.

## Telegram Commands

| Command | Behaviour |
|---------|-----------|
| `/start` | Register the user and show a welcome primer |
| `/help` | Interactive help with example queries |
| `/recent` | Most recent five saved links with summaries and tags |
| `/search <query>` | Natural-language search with entity/time parsing |
| `/stats` | Totals, top categories, top domains, last-save timestamp |
| `/export` | Send a CSV with metadata, AI summary, tags, and snapshots |
| `/archive <url>` | Force an HTML snapshot (local storage in MVP) |

Send any message containing a URL to trigger the full pipeline. Messages without URLs are treated as search prompts.

## Processing Pipeline

1. **URL detection** – Regex parse in `handlers.handle_message`.
2. **Fetch & parse** – `link_processor.process_url` resolves redirects, pulls HTML, extracts OpenGraph and HTML metadata, and computes a clean text body.
3. **Persist basics** – `database.add_link` ensures the link exists and upserts metadata, categories, entities, sources, and AI summary.
4. **AI analysis** – `link_intelligence.analyze_text_content` calls OpenAI to classify type/topics/entities and summarise the content.
5. **Embeddings** – `link_intelligence.generate_embedding` creates an OpenAI embedding and `database.store_link_embedding` keeps it for future semantic search indexes.
6. **Response** – User receives an HTML-formatted preview with summary and tags.

## Archiving Options

| Provider | Cost | Notes |
|----------|------|-------|
| Wayback Machine (Save Page Now API) | Free | Default path. Silo requests a snapshot and stores the returned archive URL. |
| Archive.today | Free | Manual form; unofficial APIs exist but unstable. |
| Browserless + Playwright | Paid (usage-based) | Run headless Chromium in the cloud; supports full-page screenshots + PDF. |
| Self-hosted Playwright | Infra cost | Run Playwright on your own server for private snapshots. |

If Wayback can’t archive the page (private URL, rate limit), Silo falls back to storing raw HTML locally in `temp_files/snapshots` so the content is still recoverable. Add Browserless/Playwright when you need visual fidelity or legally defensible copies.

## Embeddings & Semantic Search

- Default model: `text-embedding-3-small` (~1,536 dimensions, low cost).
- Generation happens asynchronously in the ingestion flow; failures are logged but do not block saving the link.
- Stored in `link_embeddings` as JSON vectors with model metadata.
- Current `/search` implementation still relies on Postgres full-text search combined with categories/entities filters; embeddings are persisted so you can attach pgvector/Pinecone later without reprocessing.
- Next steps:
  1. Add a vector index (pgvector, Chroma, or Pinecone) once you are ready for semantic retrieval.
  2. Backfill existing records by iterating through links and calling `generate_embedding`.
  3. Combine vector similarity with metadata filters for ranked results.

## Testing Strategy

See `docs/testing-plan.md` for detailed coverage, but the short version:
- **Unit tests** target pure helpers (URL parsing, metadata extraction, query parsing).
- **Integration tests** spin up a temp Postgres (or use fixtures) and assert that a mock Telegram update drives data into the DB and responds with expected text.

Run tests with `pytest` and `pytest-asyncio`:

```bash
pytest
```

## Project Structure

```
telegram_smart_agent/
├── main_bot.py          # Entrypoint wiring telegram.ext Application
├── handlers.py          # Command + message handlers
├── database.py          # Schema + persistence helpers
├── link_processor.py    # HTTP fetch + metadata extraction
├── link_intelligence.py # OpenAI-powered analysis and embeddings
├── link_retriever.py    # NLP-like search helpers
├── link_archiver.py     # Local HTML snapshots (extensible)
├── config.py            # Environment + configuration loader
├── temp_files/          # Snapshots and other artefacts
└── docs/                # Architecture, testing, and roadmap notes
```

## Maintenance Checklist

- Rotate API keys regularly; never commit `.env`.
- Monitor OpenAI usage; summarisation and embeddings both consume tokens.
- Backup Postgres or run managed. The bot depends on the DB for all state.
- Keep requirements pinned and upgrade the telegram bot SDK cautiously.

Have questions? Drop a link into the bot, or inspect the log output in your terminal for real-time traces.
