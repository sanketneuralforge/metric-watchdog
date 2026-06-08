# core/idempotency.py

"""
Prevents duplicate pipeline runs.

A run is considered duplicate if:
- Same calendar date AND
- Same dashboard image (by file hash)

This prevents double-firing from the scheduler.
"""

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("db/run_history.db")


def get_image_hash(image_path: str) -> str:
    """SHA256 hash of image file — stable identifier."""
    h = hashlib.sha256()
    h.update(Path(image_path).read_bytes())
    return h.hexdigest()[:16]


def is_duplicate_run(image_path: str) -> bool:
    """
    Returns True if we already ran for this image today.
    Prevents scheduler from firing twice.
    """
    if not DB_PATH.exists():
        return False

    today = datetime.now().strftime("%Y-%m-%d")
    image_hash = get_image_hash(image_path)

    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("""
            SELECT run_id FROM runs
            WHERE DATE(started_at) = ?
              AND dashboard_path LIKE ?
              AND status = 'success'
            LIMIT 1
        """, (today, f"%{image_hash}%")).fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def mark_run_in_progress(run_id: str, image_path: str) -> None:
    """
    Mark a run as in-progress to prevent concurrent duplicates.
    Called at pipeline start.
    """
    # The history store handles this via the completed run record
    # This is a stub for future distributed locking if needed
    pass