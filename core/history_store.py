# core/history_store.py

"""
SQLite store for run history.
Tracks every pipeline run — severity, duration, briefing text.
Queryable from the Streamlit UI history tab.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path("db/run_history.db")


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id          TEXT PRIMARY KEY,
            started_at      TEXT NOT NULL,
            duration_s      REAL,
            severity        TEXT,
            metrics_count   INTEGER,
            proven_count    INTEGER,
            unresolvable_count INTEGER,
            briefing_text   TEXT,
            briefing_html   TEXT,
            html_path       TEXT,
            status          TEXT DEFAULT 'success',
            dashboard_path  TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_run(run_result) -> None:
    """Save a completed pipeline run to history."""
    init_db()

    proven = sum(len(b.proven) for b in run_result.evidence_bundles)
    unresolvable = sum(len(b.unresolvable) for b in run_result.evidence_bundles)

    briefing = run_result.briefing
    html_path = f"db/briefing_{run_result.run_id}.html"

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT OR REPLACE INTO runs
            (run_id, started_at, duration_s, severity,
             metrics_count, proven_count, unresolvable_count,
             briefing_text, briefing_html, html_path,
             status, dashboard_path)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        run_result.run_id,
        run_result.date,
        run_result.duration_seconds,
        briefing.overall_severity if briefing else "UNKNOWN",
        len(run_result.dashboard_reading.metrics),
        proven,
        unresolvable,
        briefing.briefing_text if briefing else "",
        briefing.briefing_html if briefing else "",
        html_path,
        run_result.status,
        run_result.dashboard_reading.image_path,
    ))
    conn.commit()
    conn.close()


def get_recent_runs(limit: int = 20) -> list[dict]:
    """Fetch recent runs for the history tab."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM runs
        ORDER BY started_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_run(run_id: str) -> dict | None:
    """Fetch a specific run by ID."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None