"""
database.py - Database access layer for the Silo Link Manager bot.

This module encapsulates all direct interactions with PostgreSQL, including
schema management and the CRUD helpers used throughout the bot.
"""

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor, Json

from config import Config

logger = logging.getLogger(__name__)

config = Config()

DATABASE_URL = (
    f"postgresql://{config.DB_USER}:{config.DB_PASSWORD}"
    f"@{config.DB_HOST}:{config.DB_PORT}/{config.DB_NAME}"
)

_METADATA_SCHEMA_ENSURED = False


@contextmanager
def _connection():
    """Context manager that yields a PostgreSQL connection."""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def _cursor(*, commit: bool = False, dict_cursor: bool = False):
    """
    Context manager that yields a cursor and automatically handles commits/rollbacks.
    """
    cursor_factory = RealDictCursor if dict_cursor else None
    with _connection() as conn:
        cur = conn.cursor(cursor_factory=cursor_factory)
        try:
            yield cur
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            logger.exception("Database error")
            raise
        finally:
            cur.close()


def _drop_legacy_tables(cur) -> None:
    """
    Removes old ShopSmart tables when present so the new schema can be created.
    """
    legacy_tables = {
        "stores",
        "shopping_lists",
        "list_items",
        "shared_lists",
        "user_list_access",
        "categorizer_cache",
    }
    cur.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"
    )
    existing = {row[0] for row in cur.fetchall()}
    if legacy_tables & existing:
        logger.info("Dropping legacy ShopSmart tables: %s", legacy_tables & existing)
        cur.execute(
            """
            DROP TABLE IF EXISTS
                collection_links,
                link_snapshots,
                link_embeddings,
                link_collections,
                link_sources,
                link_entities,
                link_categories,
                link_metadata,
                links,
                users
            CASCADE;
            """
        )


def create_tables(reset: bool = False) -> None:
    """
    Creates the PostgreSQL schema required for the link manager.

    Args:
        reset: When True, drops existing link-manager tables before recreating them.
    """
    with _connection() as conn:
        cur = conn.cursor()
        try:
            if reset:
                logger.warning("Resetting database schema for link manager.")
                cur.execute(
                    """
                    DROP TABLE IF EXISTS
                        collection_links,
                        link_snapshots,
                        link_embeddings,
                        link_collections,
                        link_sources,
                        link_entities,
                        link_categories,
                        link_metadata,
                        links,
                        users
                    CASCADE;
                    """
                )
            else:
                _drop_legacy_tables(cur)

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id        BIGINT PRIMARY KEY,
                    username       VARCHAR(255),
                    language       VARCHAR(10),
                    premium_status VARCHAR(20) DEFAULT 'free',
                    created_at     TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            # Ensure new columns exist even if the table predates the migration.
            cur.execute(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS language VARCHAR(10);"
            )
            cur.execute(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS premium_status VARCHAR(20) DEFAULT 'free';"
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS links (
                    link_id         SERIAL PRIMARY KEY,
                    user_id         BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    url             TEXT NOT NULL,
                    title           TEXT,
                    description     TEXT,
                    domain          VARCHAR(255),
                    screenshot_path VARCHAR(255),
                    archived_html   TEXT,
                    ai_summary      TEXT,
                    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (user_id, url)
                );
                """
            )
            cur.execute(
                "ALTER TABLE links ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;"
            )
            cur.execute(
                "ALTER TABLE links ADD COLUMN IF NOT EXISTS screenshot_path VARCHAR(255);"
            )
            cur.execute(
                "ALTER TABLE links ADD COLUMN IF NOT EXISTS archived_html TEXT;"
            )
            cur.execute(
                "ALTER TABLE links ADD COLUMN IF NOT EXISTS ai_summary TEXT;"
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS link_metadata (
                    metadata_id  SERIAL PRIMARY KEY,
                    link_id      INT UNIQUE REFERENCES links(link_id) ON DELETE CASCADE,
                    favicon      TEXT,
                    author       VARCHAR(255),
                    publish_date TIMESTAMP WITH TIME ZONE,
                    read_time    INT,
                    content_type VARCHAR(100),
                    canonical_url TEXT,
                    language     VARCHAR(20),
                    word_count   INT
                );
                """
            )
            cur.execute(
                "ALTER TABLE link_metadata ADD COLUMN IF NOT EXISTS canonical_url TEXT;"
            )
            cur.execute(
                "ALTER TABLE link_metadata ADD COLUMN IF NOT EXISTS language VARCHAR(20);"
            )
            cur.execute(
                "ALTER TABLE link_metadata ADD COLUMN IF NOT EXISTS word_count INT;"
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS link_categories (
                    category_id SERIAL PRIMARY KEY,
                    link_id     INT REFERENCES links(link_id) ON DELETE CASCADE,
                    category    VARCHAR(100),
                    UNIQUE(link_id, category)
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS link_entities (
                    entity_id   SERIAL PRIMARY KEY,
                    link_id     INT REFERENCES links(link_id) ON DELETE CASCADE,
                    entity_type VARCHAR(100),
                    entity_name VARCHAR(255),
                    UNIQUE(link_id, entity_type, entity_name)
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS link_sources (
                    source_id          SERIAL PRIMARY KEY,
                    link_id            INT REFERENCES links(link_id) ON DELETE CASCADE,
                    shared_by_user_id  BIGINT,
                    platform           VARCHAR(100),
                    shared_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS link_collections (
                    collection_id SERIAL PRIMARY KEY,
                    user_id       BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
                    name          VARCHAR(255) NOT NULL,
                    is_public     BOOLEAN DEFAULT FALSE,
                    UNIQUE(user_id, name)
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_links (
                    collection_id INT REFERENCES link_collections(collection_id) ON DELETE CASCADE,
                    link_id       INT REFERENCES links(link_id) ON DELETE CASCADE,
                    PRIMARY KEY (collection_id, link_id)
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS link_embeddings (
                    link_id      INT PRIMARY KEY REFERENCES links(link_id) ON DELETE CASCADE,
                    embedding    JSONB NOT NULL,
                    model        VARCHAR(100),
                    created_at   TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS link_snapshots (
                    snapshot_id SERIAL PRIMARY KEY,
                    link_id     INT REFERENCES links(link_id) ON DELETE CASCADE,
                    snapshot_url TEXT,
                    created_at   TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            # Helpful indexes for lookups and search.
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_links_user_created_at ON links (user_id, created_at DESC);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_link_categories_category ON link_categories (category);"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_link_entities_name ON link_entities (entity_name);"
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_links_search
                ON links USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '')));
                """
            )

            conn.commit()
        finally:
            cur.close()


def add_user(user_id: int, username: Optional[str]) -> None:
    """Registers a Telegram user if they do not already exist."""
    with _cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO users (user_id, username)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE SET username = COALESCE(%s, users.username);
            """,
            (user_id, username, username),
        )


def add_link(
    user_id: int,
    url: str,
    *,
    title: Optional[str] = None,
    description: Optional[str] = None,
    domain: Optional[str] = None,
) -> Optional[int]:
    """Adds or updates a link and returns its link_id."""
    with _cursor(commit=True) as cur:
        try:
            cur.execute(
                """
                INSERT INTO links (user_id, url, title, description, domain)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id, url)
                DO UPDATE SET
                    title       = COALESCE(EXCLUDED.title, links.title),
                    description = COALESCE(EXCLUDED.description, links.description),
                    domain      = COALESCE(EXCLUDED.domain, links.domain),
                    updated_at  = CURRENT_TIMESTAMP
                RETURNING link_id;
                """,
                (user_id, url, title, description, domain),
            )
            result = cur.fetchone()
            return result[0] if result else None
        except psycopg2.Error:
            logger.exception("Failed to add/update link for user %s", user_id)
            return None


def update_link_details(
    link_id: int,
    *,
    title: Optional[str] = None,
    description: Optional[str] = None,
    domain: Optional[str] = None,
    screenshot_path: Optional[str] = None,
    archived_html: Optional[str] = None,
    ai_summary: Optional[str] = None,
) -> None:
    """Updates selected columns on the links row."""
    assignments: List[str] = []
    values: List[Any] = []

    def _add(column: str, value: Optional[Any]) -> None:
        if value is not None:
            assignments.append(f"{column} = %s")
            values.append(value)

    _add("title", title)
    _add("description", description)
    _add("domain", domain)
    _add("screenshot_path", screenshot_path)
    _add("archived_html", archived_html)
    _add("ai_summary", ai_summary)

    if not assignments:
        return

    assignments.append("updated_at = CURRENT_TIMESTAMP")
    values.append(link_id)

    query = f"UPDATE links SET {', '.join(assignments)} WHERE link_id = %s;"

    with _cursor(commit=True) as cur:
        cur.execute(query, values)


def _parse_datetime(candidate: Any) -> Optional[datetime]:
    """Best-effort parsing for timestamps that might arrive as strings."""
    if candidate in (None, "", "null"):
        return None
    if isinstance(candidate, datetime):
        return candidate
    try:
        candidate_str = str(candidate).strip()
        if candidate_str.endswith("Z"):
            candidate_str = candidate_str[:-1] + "+00:00"
        return datetime.fromisoformat(candidate_str)
    except ValueError:
        return None


def add_link_metadata(link_id: int, metadata: Dict[str, Any]) -> None:
    """Upserts metadata for a link."""
    if not metadata:
        return

    publish_date = _parse_datetime(metadata.get("publish_date"))
    read_time = metadata.get("read_time")
    try:
        read_time = int(read_time) if read_time is not None else None
    except (TypeError, ValueError):
        read_time = None

    with _cursor(commit=True) as cur:
        _ensure_link_metadata_columns(cur)
        cur.execute(
            """
            INSERT INTO link_metadata (link_id, favicon, author, publish_date, read_time, content_type, canonical_url, language, word_count)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (link_id) DO UPDATE SET
                favicon      = COALESCE(EXCLUDED.favicon, link_metadata.favicon),
                author       = COALESCE(EXCLUDED.author, link_metadata.author),
                publish_date = COALESCE(EXCLUDED.publish_date, link_metadata.publish_date),
                read_time    = COALESCE(EXCLUDED.read_time, link_metadata.read_time),
                content_type = COALESCE(EXCLUDED.content_type, link_metadata.content_type),
                canonical_url = COALESCE(EXCLUDED.canonical_url, link_metadata.canonical_url),
                language     = COALESCE(EXCLUDED.language, link_metadata.language),
                word_count   = COALESCE(EXCLUDED.word_count, link_metadata.word_count);
            """,
            (
                link_id,
                metadata.get("favicon"),
                metadata.get("author"),
                publish_date,
                read_time,
                metadata.get("content_type"),
                metadata.get("canonical_url"),
                metadata.get("language"),
                metadata.get("word_count"),
            ),
        )


def add_link_categories(link_id: int, categories: Iterable[str]) -> None:
    """Adds distinct categories for a link."""
    if not categories:
        return

    with _cursor(commit=True) as cur:
        for category in {c.strip() for c in categories if c}:
            cur.execute(
                """
                INSERT INTO link_categories (link_id, category)
                VALUES (%s, %s)
                ON CONFLICT (link_id, category) DO NOTHING;
                """,
                (link_id, category),
            )


def add_link_entities(link_id: int, entities: Iterable[Dict[str, Any]]) -> None:
    """Stores extracted entities for a link."""
    if not entities:
        return

    with _cursor(commit=True) as cur:
        for entity in entities:
            entity_name = entity.get("name")
            entity_type = entity.get("type")
            if not entity_name:
                continue
            cur.execute(
                """
                INSERT INTO link_entities (link_id, entity_type, entity_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (link_id, entity_type, entity_name) DO NOTHING;
                """,
                (link_id, entity_type, entity_name),
            )


def record_link_source(
    link_id: int,
    *,
    shared_by_user_id: Optional[int],
    platform: Optional[str] = None,
    shared_at: Optional[datetime] = None,
) -> None:
    """Tracks how the link was shared with the bot."""
    with _cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO link_sources (link_id, shared_by_user_id, platform, shared_at)
            VALUES (%s, %s, %s, %s);
            """,
            (link_id, shared_by_user_id, platform, shared_at or datetime.utcnow()),
        )


def add_link_snapshot(link_id: int, snapshot_url: str) -> None:
    """Stores a snapshot URL for a given link."""
    if not snapshot_url:
        return
    with _cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO link_snapshots (link_id, snapshot_url)
            VALUES (%s, %s);
            """,
            (link_id, snapshot_url),
        )


def store_link_embedding(link_id: int, embedding: Iterable[float], model: Optional[str]) -> None:
    """Persists an embedding vector for a link."""
    if not embedding:
        return

    with _cursor(commit=True) as cur:
        cur.execute(
            """
            INSERT INTO link_embeddings (link_id, embedding, model)
            VALUES (%s, %s, %s)
            ON CONFLICT (link_id) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                model     = EXCLUDED.model,
                created_at = CURRENT_TIMESTAMP;
            """,
            (link_id, Json(list(embedding)), model),
        )


def _ensure_link_metadata_columns(cur) -> None:
    """Adds newer link_metadata columns when running against an older schema."""
    global _METADATA_SCHEMA_ENSURED
    if _METADATA_SCHEMA_ENSURED:
        return

    cur.execute("ALTER TABLE link_metadata ADD COLUMN IF NOT EXISTS canonical_url TEXT;")
    cur.execute("ALTER TABLE link_metadata ADD COLUMN IF NOT EXISTS language VARCHAR(20);")
    cur.execute("ALTER TABLE link_metadata ADD COLUMN IF NOT EXISTS word_count INT;")
    _METADATA_SCHEMA_ENSURED = True


def get_recent_links(user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """Returns the most recently saved links for a user."""
    with _cursor(dict_cursor=True) as cur:
        cur.execute(
            """
            SELECT
                l.link_id,
                l.url,
                COALESCE(l.title, l.url) AS title,
                l.description,
                l.ai_summary,
                l.domain,
                l.created_at,
                ARRAY(
                    SELECT lc.category FROM link_categories lc WHERE lc.link_id = l.link_id ORDER BY lc.category
                ) AS categories
            FROM links l
            WHERE l.user_id = %s
            ORDER BY l.created_at DESC
            LIMIT %s;
            """,
            (user_id, limit),
        )
        return cur.fetchall()


def search_links(user_id: int, query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Performs a lightweight semantic search using text rank and category/entity matches.
    """
    if not query:
        return []

    with _cursor(dict_cursor=True) as cur:
        cur.execute(
            """
            WITH ranked_links AS (
                SELECT
                    l.link_id,
                    l.url,
                    COALESCE(l.title, l.url) AS title,
                    l.description,
                    l.ai_summary,
                    l.domain,
                    l.created_at,
                    ts_rank_cd(
                        to_tsvector('english', coalesce(l.title, '') || ' ' || coalesce(l.description, '')),
                        plainto_tsquery('english', %s)
                    ) AS relevance
                FROM links l
                WHERE l.user_id = %s
            )
            SELECT
                rl.*,
                ARRAY(
                    SELECT lc.category FROM link_categories lc WHERE lc.link_id = rl.link_id ORDER BY lc.category
                ) AS categories,
                ARRAY(
                    SELECT le.entity_name FROM link_entities le WHERE le.link_id = rl.link_id ORDER BY le.entity_name
                ) AS entities
            FROM ranked_links rl
            WHERE rl.relevance > 0
            ORDER BY rl.relevance DESC, rl.created_at DESC
            LIMIT %s;
            """,
            (query, user_id, limit),
        )
        results = cur.fetchall()

    # Fallback to ILIKE matching when ts_vector yields nothing.
    if results:
        return results

    pattern = f"%{query}%"
    with _cursor(dict_cursor=True) as cur:
        cur.execute(
            """
            SELECT
                l.link_id,
                l.url,
                COALESCE(l.title, l.url) AS title,
                l.description,
                l.ai_summary,
                l.domain,
                l.created_at,
                ARRAY(
                    SELECT lc.category FROM link_categories lc WHERE lc.link_id = l.link_id
                ) AS categories,
                ARRAY(
                    SELECT le.entity_name FROM link_entities le WHERE le.link_id = l.link_id
                ) AS entities
            FROM links l
            WHERE l.user_id = %s
              AND (
                    l.title ILIKE %s
                 OR l.description ILIKE %s
                 OR EXISTS (
                        SELECT 1 FROM link_categories lc WHERE lc.link_id = l.link_id AND lc.category ILIKE %s
                    )
                 OR EXISTS (
                        SELECT 1 FROM link_entities le WHERE le.link_id = l.link_id AND le.entity_name ILIKE %s
                    )
              )
            ORDER BY l.created_at DESC
            LIMIT %s;
            """,
            (user_id, pattern, pattern, pattern, pattern, limit),
        )
        return cur.fetchall()


def get_link_stats(user_id: int) -> Dict[str, Any]:
    """Aggregates high-level stats used by the /stats command."""
    stats: Dict[str, Any] = {"total_links": 0, "top_categories": [], "top_domains": [], "last_saved_at": None}

    with _cursor(dict_cursor=True) as cur:
        cur.execute("SELECT COUNT(*) AS total FROM links WHERE user_id = %s;", (user_id,))
        row = cur.fetchone()
        stats["total_links"] = row["total"] if row else 0

        cur.execute(
            """
            SELECT category, COUNT(*) AS count
            FROM link_categories lc
            JOIN links l ON lc.link_id = l.link_id
            WHERE l.user_id = %s
            GROUP BY category
            ORDER BY count DESC
            LIMIT 5;
            """,
            (user_id,),
        )
        stats["top_categories"] = cur.fetchall()

        cur.execute(
            """
            SELECT domain, COUNT(*) AS count
            FROM links
            WHERE user_id = %s AND domain IS NOT NULL
            GROUP BY domain
            ORDER BY count DESC
            LIMIT 5;
            """,
            (user_id,),
        )
        stats["top_domains"] = cur.fetchall()

        cur.execute(
            """
            SELECT created_at
            FROM links
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 1;
            """,
            (user_id,),
        )
        last_row = cur.fetchone()
        stats["last_saved_at"] = last_row["created_at"] if last_row else None

    return stats


def get_links_for_export(user_id: int) -> List[Dict[str, Any]]:
    """Returns all links and annotations needed for export."""
    with _cursor(dict_cursor=True) as cur:
        cur.execute(
            """
            SELECT
                l.link_id,
                l.url,
                COALESCE(l.title, l.url) AS title,
                l.description,
                l.ai_summary,
                l.domain,
                l.created_at,
                l.updated_at,
                lm.author,
                lm.publish_date,
                lm.read_time,
                lm.content_type,
                ARRAY(
                    SELECT lc.category FROM link_categories lc WHERE lc.link_id = l.link_id ORDER BY lc.category
                ) AS categories,
                ARRAY(
                    SELECT le.entity_name FROM link_entities le WHERE le.link_id = l.link_id ORDER BY le.entity_name
                ) AS entities,
                ARRAY(
                    SELECT ls.snapshot_url FROM link_snapshots ls WHERE ls.link_id = l.link_id ORDER BY ls.created_at DESC
                ) AS snapshots
            FROM links l
            LEFT JOIN link_metadata lm ON lm.link_id = l.link_id
            WHERE l.user_id = %s
            ORDER BY l.created_at DESC;
            """,
            (user_id,),
        )
        return cur.fetchall()


def get_link_by_id(link_id: int) -> Optional[Dict[str, Any]]:
    """Fetches a single link by primary key."""
    with _cursor(dict_cursor=True) as cur:
        cur.execute(
            """
            SELECT
                l.*,
                lm.favicon,
                lm.author,
                lm.publish_date,
                lm.read_time,
                lm.content_type
            FROM links l
            LEFT JOIN link_metadata lm ON lm.link_id = l.link_id
            WHERE l.link_id = %s;
            """,
            (link_id,),
        )
        return cur.fetchone()


if __name__ == "__main__":
    create_tables()
    print("Database tables for Silo created successfully.")
