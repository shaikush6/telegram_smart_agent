"""
link_archiver.py - Handles link archiving and snapshots.

The pipeline attempts a Wayback Machine snapshot first, then captures a local HTML
backup so content is still recoverable when the remote archive fails.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

import database
from config import Config
from link_processor import process_url

logger = logging.getLogger(__name__)

config = Config()
SNAPSHOT_DIR = Path(config.TEMP_DIR) / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

WAYBACK_SAVE_ENDPOINT = "https://web.archive.org/save/"


async def archive_link(link_id: int, url: str) -> Optional[str]:
    """
    Attempts to archive the provided URL using the Wayback Machine, falling back to a
    local HTML snapshot. Returns a path or URL describing where the archive lives.
    """
    wayback_snapshot = await _attempt_wayback_snapshot(url)
    if wayback_snapshot:
        database.add_link_snapshot(link_id, wayback_snapshot)
        return wayback_snapshot

    loop = asyncio.get_running_loop()
    try:
        local_path = await loop.run_in_executor(None, _save_local_snapshot, link_id, url)
        if local_path:
            database.add_link_snapshot(link_id, local_path)
        return local_path
    except Exception:
        logger.exception("Failed to archive %s locally", url)
        return None


async def _attempt_wayback_snapshot(url: str) -> Optional[str]:
    """
    Calls the Wayback Machine Save Page Now endpoint. Returns the archive URL on success.
    This call is best-effort; errors are logged and treated as non-fatal.
    """
    loop = asyncio.get_running_loop()

    def _request_snapshot() -> Optional[str]:
        try:
            headers = {"User-Agent": "SiloBot/1.0 (+https://telegram.me/silo)"}
            response = requests.get(
                f"{WAYBACK_SAVE_ENDPOINT}{url}",
                headers=headers,
                timeout=20,
                allow_redirects=False,
            )
            if response.status_code in (200, 201, 202):
                archive_url = response.headers.get("Content-Location")
                if archive_url:
                    if not archive_url.startswith("http"):
                        archive_url = f"https://web.archive.org{archive_url}"
                    return archive_url
            logger.info(
                "Wayback snapshot failed for %s with status %s",
                url,
                response.status_code,
            )
        except Exception as exc:  # noqa: broad-except - network issues shouldn't break ingestion
            logger.warning("Wayback snapshot error for %s: %s", url, exc)
        return None

    return await loop.run_in_executor(None, _request_snapshot)


def _save_local_snapshot(link_id: int, url: str) -> Optional[str]:
    page = process_url(url)
    if not page or not page.get("html"):
        return None

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    snapshot_path = SNAPSHOT_DIR / f"link_{link_id}_{timestamp}.html"
    snapshot_path.write_text(page["html"], encoding="utf-8")
    database.update_link_details(link_id, archived_html=page["html"])
    return str(snapshot_path)
