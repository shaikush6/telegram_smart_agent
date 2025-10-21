# Product Brief: Silo Link Intelligence Bot

## Vision
Help teams remember and reuse the important links shared across chats. Silo turns Telegram into a lightweight knowledge base by classifying, tagging, and archiving every URL that flows through a conversation.

## Goals
- **MVP success metric**: Every saved link returns in `/recent` within 3 seconds and is searchable via `/search`.
- **Adoption**: Pilot with 20 power users; convert at least half to weekly active users.
- **Quality**: Maintain <1% ingestion failures (network + AI combined) measured over 7-day windows.

## User Stories
1. “I drop a link in Telegram and instantly get a summary with tags so I know if it is worth reading now.”
2. “I can ask ‘docs Sarah shared last week about onboarding’ and Silo finds them without remembering URLs.”
3. “For critical resources, I can archive snapshots so the content is still available months later.”

## Scope by Phase

### MVP (week 1)
- Telegram commands `/start`, `/help`, `/recent`, `/search`, `/stats`, `/export`, `/archive`.
- Link ingestion with AI summary, topics, entities, categories.
- Postgres schema (links, metadata, categories, entities, sources, snapshots, embeddings).
- Local HTML snapshot storage.
- CSV export for quick backups.

### Phase 2 (week 2–3)
- Robust search: combine embeddings with metadata filters.
- Entity filters (e.g., “from Sarah”, “articles about onboarding”).
- Incremental archiving provider (Wayback Machine integration).
- Health monitoring: link status checks and retry queue.

### Phase 3 (week 4+)
- Shared collections and collaborative tagging.
- Email or Telegram digest of new/highlighted links.
- Web dashboard for browsing, editing, and sharing outside Telegram.
- Advanced archiving (screenshots, PDF capture) via Browserless/Playwright.

## Functional Requirements
- Detect URLs in any incoming message, even when multiple links appear.
- Deduplicate per user: same user + URL combination should update metadata rather than duplicate rows.
- Persist AI output (summary, topics, entities) and attach categories/entities to link records.
- Generate and store OpenAI embeddings for future semantic search.
- Provide HTML-formatted responses with safe escaping.
- Export command must deliver a CSV with all relevant annotations in under 10 seconds for 1,000 links.

## Non-Functional Requirements
- **Reliability**: Bot should continue processing even if AI or embedding calls fail (log + degrade gracefully).
- **Security**: No secrets logged. `.env` values only loaded locally. Postgres credentials required.
- **Performance**: Ingestion cycle target <2 seconds for average page (excluding AI latency).
- **Cost awareness**: Default to cost-effective OpenAI models (`gpt-4o-mini`, `text-embedding-3-small`).

## Integrations
- **Telegram**: python-telegram-bot v20.x, long polling.
- **OpenAI**: Chat completions for summaries and classification; embeddings API for semantic vectors.
- **Archiving**: Local HTML snapshot now; plan for Wayback Machine or Browserless.
- **PostgreSQL**: Primary data store. Optional pgvector extension later.

## Open Questions / Future Decisions
- Authentication & multi-user workspace design once shared collections ship.
- Choosing between pgvector vs. managed vector databases once semantic search is in production.
- Handling private/internal URLs (redaction, secure storage, access controls).
- Background job infrastructure (Celery vs. RQ) for heavy operations (archiving, link health checks).

## Risks & Mitigations
- **OpenAI downtime** → Fall back to storing metadata only; cue retry job to fill AI fields later.
- **Large pages/timeouts** → Enforce fetch timeout (12s) and size limits; optionally integrate a scraping proxy.
- **Spam or malicious links** → Add domain allowlist/denylist controls and rate limiting per user.

Silo’s foundation is now refocused on link intelligence. The next steps are semantic retrieval, richer archiving, and collaboration features once the MVP is stable.
