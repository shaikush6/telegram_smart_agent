# Silo Architecture & Operations

## System Overview
- **Entry point**: `main_bot.py` initialises `python-telegram-bot` application, registers command and message handlers, and starts polling.
- **Handlers**: `handlers.py` orchestrates command responses, URL ingestion, and natural-language searches.
- **Data layer**: `database.py` owns schema creation, connection helpers, CRUD utilities, and analytics queries.
- **Processing**:
  - `link_processor.py` fetches pages with a desktop User-Agent, extracts structured metadata, and produces cleaned text.
  - `link_intelligence.py` talks to OpenAI for content classification, summaries, and embeddings.
  - `link_retriever.py` maps user queries to database lookups and date filters.
  - `link_archiver.py` holds the snapshot logic (local HTML today, pluggable for external services).

```
Telegram update ──▶ handlers.handle_message
                  ├─▶ URL? process_url() ─▶ database persistence ─▶ AI analysis / embeddings ─▶ response
                  └─▶ Natural-language query? find_links_by_query() ─▶ search response
```

## Database Schema Highlights
- `links`: core table with URL, title, description, AI summary, timestamps, domain, and archival pointers.
- `link_metadata`: per-link metadata (favicon, author, publish date, language, canonical URL, word count).
- `link_categories` and `link_entities`: AI-derived tags and entities for filtering.
- `link_embeddings`: JSONB storage of OpenAI vectors with model name and timestamp, ready for future vector indexes.
- `link_snapshots`: references to saved HTML (or external archive URLs later).
- Auxiliary tables for collections, sources, and relationships allow future collaboration features.

Run `database.create_tables()` once per environment to ensure migrations are applied.

## Archiving Strategy

### Current Behaviour
- First attempt: Wayback Machine Save Page Now (no API key required). On success, Silo stores the archive URL returned in the `Content-Location` header.
- Fallback: save raw HTML to `temp_files/snapshots` and keep the body in `links.archived_html` for local recovery.

### Production Options

| Service | Price model | What you get | When to use |
|---------|-------------|--------------|-------------|
| Wayback Machine (Save Page Now API) | Free, rate-limited | Public, timestamped archive URL | Default for public pages, legal/audit needs |
| Archive.today | Free, manual/unstable APIs | Public snapshot; sometimes blocked by sites | Fallback when Wayback fails |
| Browserless + Playwright | Usage-based (from ~$10/mo) | Automated headless browser; take PDF/JPEG/HTML | Private archives, screenshots, auth flows |
| Self-hosted Playwright | Infra cost only | Full control, store binary assets | Sensitive data, air-gapped deployments |

**Recommendation**: Keep the Wayback-first flow with local fallback. Add Browserless (or self-hosted Playwright) for high-fidelity captures, authenticated sessions, or when legal compliance demands private storage.

## Embeddings & Semantic Search
- Default embedding model: `text-embedding-3-small` (cheap, 1,536 dimensions).
- Generation is asynchronous; failures fall back silently to keep ingestion resilient.
- Vectors are stored in JSONB so you can migrate later without schema churn.
- Today, `/search` still relies on Postgres full-text + metadata filters; embeddings are persisted but not yet queried.
- Next steps:
  1. Enable pgvector (`CREATE EXTENSION vector;`) and add a `VECTOR(1536)` column, or
  2. Stream vectors into a managed service (Pinecone, Weaviate, Chroma Cloud).
  3. Implement semantic ranking by combining cosine similarity with metadata filters.
- For backfill, iterate over existing links, call `link_intelligence.generate_embedding`, and store results.

## Testing & Quality Gates
- **Unit tests** focus on pure helpers (metadata extraction, query parsing, database utility functions using mocks).
- **Integration tests** hit a temporary Postgres (use fixtures or Docker) and run the full handler pipeline with a fake Telegram update.
- Run tests with `pytest` and `pytest-asyncio`; see `docs/testing-plan.md` for detailed scenarios.
- Enable logging (`export LOGLEVEL=INFO`) during tests to capture pipeline traces.

## Deployment Notes
- Keep `.env` out of version control. Use environment variables in production.
- Rotate API keys regularly and monitor OpenAI usage (summaries + embeddings consume tokens).
- PostgreSQL is the single source of truth; back it up.
- If you introduce background jobs (snapshots, health checks), reuse the modules here and enqueue via Celery or RQ; most functions are already idempotent.

## Roadmap Hooks
- `link_retriever` structure leaves room for semantic search and notifications.
- `link_archiver` can be swapped with an async client for Wayback or Browserless with minimal surface change.
- `link_embeddings` table only stores data; retrieval side can be implemented later without data migration.
