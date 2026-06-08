# observability/tracer.py

"""
Span-level run tracer for Metric Watchdog.
Tracks every LLM call, SQL query, and stage with:
- Latency
- Token count
- Model used
- Status (success/error)

Stored in SQLite — queryable from Streamlit UI.
"""

import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

DB_PATH = Path("db/traces.db")


def init_tracer_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS spans (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          TEXT NOT NULL,
            span_id         TEXT NOT NULL,
            stage           TEXT NOT NULL,
            model           TEXT,
            input_tokens    INTEGER DEFAULT 0,
            output_tokens   INTEGER DEFAULT 0,
            latency_ms      INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'success',
            error           TEXT,
            metadata        TEXT,
            started_at      TEXT NOT NULL,
            finished_at     TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_metrics (
            run_id          TEXT PRIMARY KEY,
            date            TEXT NOT NULL,
            severity        TEXT,
            total_spans     INTEGER DEFAULT 0,
            error_spans     INTEGER DEFAULT 0,
            total_tokens    INTEGER DEFAULT 0,
            total_latency_ms INTEGER DEFAULT 0,
            estimated_cost  REAL DEFAULT 0,
            metrics_read    INTEGER DEFAULT 0,
            proven_claims   INTEGER DEFAULT 0,
            unresolved_gaps INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'success'
        )
    """)
    conn.commit()
    conn.close()


@dataclass
class Span:
    run_id: str
    span_id: str
    stage: str
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    status: str = "success"
    error: str = ""
    metadata: dict = field(default_factory=dict)
    started_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )
    finished_at: str = ""
    _start_time: float = field(default_factory=time.time)

    def estimate_tokens(self, input_text: str, output_text: str):
        self.input_tokens = len(input_text) // 4
        self.output_tokens = len(output_text) // 4


class RunTracer:
    """
    Span-level tracer for a single pipeline run.
    Usage:
        tracer = RunTracer(run_id)
        span = tracer.start_span("sql_writer", model="llama-3.3-70b")
        # ... do work ...
        span.estimate_tokens(input, output)
        tracer.finish_span(span, status="success")
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.spans: list[Span] = []
        self._span_counter = 0
        init_tracer_db()

    def start_span(
        self,
        stage: str,
        model: str = "",
        metadata: dict = None,
    ) -> Span:
        self._span_counter += 1
        span = Span(
            run_id=self.run_id,
            span_id=f"{self.run_id}_{self._span_counter:03d}",
            stage=stage,
            model=model,
            metadata=metadata or {},
            _start_time=time.time(),
        )
        return span

    def finish_span(
        self,
        span: Span,
        status: str = "success",
        error: str = "",
    ):
        span.finished_at = datetime.now().isoformat()
        span.latency_ms = int((time.time() - span._start_time) * 1000)
        span.status = status
        span.error = error
        self.spans.append(span)
        self._save_span(span)

    def _save_span(self, span: Span):
        import json
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO spans
                (run_id, span_id, stage, model, input_tokens,
                 output_tokens, latency_ms, status, error,
                 metadata, started_at, finished_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            span.run_id, span.span_id, span.stage, span.model,
            span.input_tokens, span.output_tokens, span.latency_ms,
            span.status, span.error,
            json.dumps(span.metadata),
            span.started_at, span.finished_at,
        ))
        conn.commit()
        conn.close()

    def save_run_metrics(
        self,
        severity: str,
        metrics_read: int = 0,
        proven_claims: int = 0,
        unresolved_gaps: int = 0,
        estimated_cost: float = 0.0,
        status: str = "success",
    ):
        """Save aggregated run metrics after pipeline completes."""
        total_tokens = sum(
            s.input_tokens + s.output_tokens for s in self.spans
        )
        total_latency = sum(s.latency_ms for s in self.spans)
        error_spans = sum(1 for s in self.spans if s.status == "error")

        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT OR REPLACE INTO run_metrics
                (run_id, date, severity, total_spans, error_spans,
                 total_tokens, total_latency_ms, estimated_cost,
                 metrics_read, proven_claims, unresolved_gaps, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            self.run_id,
            datetime.now().strftime("%Y-%m-%d"),
            severity,
            len(self.spans),
            error_spans,
            total_tokens,
            total_latency,
            estimated_cost,
            metrics_read,
            proven_claims,
            unresolved_gaps,
            status,
        ))
        conn.commit()
        conn.close()

    def get_summary(self) -> dict:
        total_tokens = sum(
            s.input_tokens + s.output_tokens for s in self.spans
        )
        error_count = sum(1 for s in self.spans if s.status == "error")
        return {
            "run_id": self.run_id,
            "total_spans": len(self.spans),
            "error_spans": error_count,
            "total_tokens": total_tokens,
            "total_latency_ms": sum(s.latency_ms for s in self.spans),
        }


def get_recent_traces(limit: int = 10) -> list[dict]:
    """Fetch recent run metrics for the observability tab."""
    init_tracer_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM run_metrics
        ORDER BY date DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_spans_for_run(run_id: str) -> list[dict]:
    """Fetch all spans for a specific run."""
    init_tracer_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT * FROM spans
        WHERE run_id = ?
        ORDER BY id ASC
    """, (run_id,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]