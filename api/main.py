# api/main.py

"""
FastAPI REST layer for Metric Watchdog.
Exposes the pipeline as an API endpoint.

Endpoints:
  GET  /health          — system health check
  POST /run             — trigger pipeline with dashboard path
  POST /run/upload      — trigger pipeline with uploaded image
  GET  /runs            — list recent runs
  GET  /runs/{run_id}   — get specific run
  GET  /metrics         — production metrics
  GET  /alerts          — active alerts
"""

import tempfile
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from api.schemas import RunRequest, RunResponse, HealthResponse
from config.settings import settings
from core.history_store import get_recent_runs, get_run, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    from observability.tracer import init_tracer_db
    init_tracer_db()
    yield


app = FastAPI(
    title="Metric Watchdog API",
    version="1.0.0",
    description="Autonomous morning intelligence agent — REST API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health():
    """System health check — verifies all connections."""
    postgres_ok = False
    try:
        from core.db import execute_query
        execute_query("SELECT 1")
        postgres_ok = True
    except Exception:
        pass

    recent = get_recent_runs(limit=1)
    last = recent[0] if recent else None

    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "vision_provider": settings.vision_provider,
        "postgres_connected": postgres_ok,
        "last_run_id": last["run_id"] if last else None,
        "last_run_severity": last["severity"] if last else None,
    }


# ── Pipeline trigger ──────────────────────────────────────────────

@app.post("/run", response_model=RunResponse)
def run_pipeline_endpoint(req: RunRequest):
    """
    Trigger pipeline with a dashboard path on the server filesystem.
    Use this when the dashboard image is already on disk
    (e.g. scheduled screenshot from a BI tool).
    """
    if not Path(req.dashboard_path).exists():
        raise HTTPException(
            404,
            f"Dashboard image not found: {req.dashboard_path}"
        )

    schema = None
    if req.schema_path:
        from core.schema import load_from_file
        schema = load_from_file(req.schema_path)

    # Bypass idempotency if force=True
    if not req.force:
        from core.idempotency import is_duplicate_run
        if is_duplicate_run(req.dashboard_path):
            raise HTTPException(
                409,
                "Duplicate run detected — already ran for this dashboard today. "
                "Use force=true to override."
            )

    from agents.orchestrator import run_pipeline
    result = run_pipeline(req.dashboard_path, schema=schema)

    return _build_response(result)


@app.post("/run/upload", response_model=RunResponse)
async def run_pipeline_upload(file: UploadFile = File(...)):
    """
    Trigger pipeline with an uploaded dashboard image.
    Use this when uploading screenshots directly from a client.
    """
    suffix = Path(file.filename or "dashboard.png").suffix or ".png"

    with tempfile.NamedTemporaryFile(
        suffix=suffix, delete=False
    ) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from agents.orchestrator import run_pipeline
        result = run_pipeline(tmp_path)
        return _build_response(result)
    finally:
        os.unlink(tmp_path)


# ── Run history ───────────────────────────────────────────────────

@app.get("/runs")
def list_runs(limit: int = 20):
    """List recent pipeline runs."""
    runs = get_recent_runs(limit=limit)
    return {"runs": runs, "total": len(runs)}


@app.get("/runs/{run_id}")
def get_run_detail(run_id: str):
    """Get details of a specific run."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run '{run_id}' not found")
    return run


@app.get("/runs/{run_id}/briefing", response_class=HTMLResponse)
def get_briefing_html(run_id: str):
    """Get the HTML briefing for a specific run."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, f"Run '{run_id}' not found")
    html = run.get("briefing_html", "")
    if not html:
        raise HTTPException(404, "No HTML briefing for this run")
    return HTMLResponse(content=html)


# ── Observability ─────────────────────────────────────────────────

@app.get("/metrics")
def get_metrics(days: int = 7):
    """Production metrics for the last N days."""
    from observability.metrics import get_production_metrics
    return get_production_metrics(days=days)


@app.get("/alerts")
def get_alerts(days: int = 7):
    """Active alert rules."""
    from observability.alerts import evaluate_alert_rules
    alerts = evaluate_alert_rules(days=days)
    return {
        "alerts": [
            {
                "level": a.level,
                "rule": a.rule,
                "message": a.message,
                "value": a.value,
                "threshold": a.threshold,
            }
            for a in alerts
        ],
        "count": len(alerts),
    }


# ── Helper ────────────────────────────────────────────────────────

def _build_response(result) -> RunResponse:
    briefing = result.briefing
    proven = sum(len(b.proven) for b in result.evidence_bundles)
    unresolved = sum(len(b.unresolvable) for b in result.evidence_bundles)

    return RunResponse(
        run_id=result.run_id,
        severity=briefing.overall_severity if briefing else "UNKNOWN",
        metrics_read=len(result.dashboard_reading.metrics),
        proven_claims=proven,
        unresolved_gaps=unresolved,
        duration_seconds=result.duration_seconds,
        status=result.status,
        briefing_summary=(
            briefing.executive_summary[:200] if briefing else ""
        ),
        html_path=f"db/briefing_{result.run_id}.html",
    )