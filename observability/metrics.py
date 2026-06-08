# observability/metrics.py

"""
Production metrics for Metric Watchdog.
Computed from the traces database.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("db/traces.db")


def get_production_metrics(days: int = 7) -> dict:
    """
    Compute production metrics over the last N days.
    Returns metrics suitable for the observability dashboard.
    """
    if not DB_PATH.exists():
        return _empty_metrics()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Total runs and completion rate
    runs = conn.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
            AVG(total_tokens) as avg_tokens,
            SUM(estimated_cost) as total_cost,
            AVG(total_latency_ms) as avg_latency_ms,
            SUM(proven_claims) as total_proven,
            SUM(unresolved_gaps) as total_unresolved
        FROM run_metrics
        WHERE date >= DATE('now', ?)
    """, (f"-{days} days",)).fetchone()

    # Error rate by stage
    stage_errors = conn.execute("""
        SELECT stage, COUNT(*) as errors
        FROM spans
        WHERE status = 'error'
          AND started_at >= DATETIME('now', ?)
        GROUP BY stage
        ORDER BY errors DESC
    """, (f"-{days} days",)).fetchall()

    # Severity distribution
    severity_dist = conn.execute("""
        SELECT severity, COUNT(*) as count
        FROM run_metrics
        WHERE date >= DATE('now', ?)
        GROUP BY severity
    """, (f"-{days} days",)).fetchall()

    # Latency by stage (p50, p95)
    stage_latency = conn.execute("""
        SELECT
            stage,
            AVG(latency_ms) as avg_ms,
            MAX(latency_ms) as max_ms,
            COUNT(*) as calls
        FROM spans
        WHERE started_at >= DATETIME('now', ?)
        GROUP BY stage
        ORDER BY avg_ms DESC
    """, (f"-{days} days",)).fetchall()

    conn.close()

    total = runs["total"] or 0
    successful = runs["successful"] or 0
    completion_rate = (successful / total * 100) if total > 0 else 0

    return {
        "total_runs": total,
        "successful_runs": successful,
        "failed_runs": runs["failed"] or 0,
        "completion_rate_pct": round(completion_rate, 1),
        "avg_tokens_per_run": int(runs["avg_tokens"] or 0),
        "total_cost_usd": round(runs["total_cost"] or 0, 4),
        "avg_latency_ms": int(runs["avg_latency_ms"] or 0),
        "total_proven_claims": runs["total_proven"] or 0,
        "total_unresolved_gaps": runs["total_unresolved"] or 0,
        "stage_errors": [dict(r) for r in stage_errors],
        "severity_distribution": {
            r["severity"]: r["count"]
            for r in severity_dist
        },
        "stage_latency": [dict(r) for r in stage_latency],
    }


def _empty_metrics() -> dict:
    return {
        "total_runs": 0,
        "successful_runs": 0,
        "failed_runs": 0,
        "completion_rate_pct": 0,
        "avg_tokens_per_run": 0,
        "total_cost_usd": 0,
        "avg_latency_ms": 0,
        "total_proven_claims": 0,
        "total_unresolved_gaps": 0,
        "stage_errors": [],
        "severity_distribution": {},
        "stage_latency": [],
    }