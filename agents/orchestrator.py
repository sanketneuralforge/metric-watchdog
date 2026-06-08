# agents/orchestrator.py

import os
import time
from datetime import datetime

from core.models import RunResult
from core.schema import SchemaContext, discover_from_postgres
from core.run_logger import RunLog
from core.history_store import save_run, init_db
from core import db
from agents import reader_agent, reasoning_agent, diagnosis_agent, narrator_agent
from delivery import email_sender, slack_sender
from config.settings import settings


def run_pipeline(
    image_path: str,
    schema: SchemaContext | None = None,
) -> RunResult:
    """
    Full pipeline: Read → Reason → Diagnose → Narrate → Deliver.
    Logs every stage to plain text log file.
    Saves run to history store.
    """
    run_id = f"watchdog_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # ── Initialize logger ────────────────────────────────────────
    log = RunLog(run_id)
    log.pipeline_start(image_path)

    start = time.time()

    # ── Schema ───────────────────────────────────────────────────
    if schema is None:
        log.info("schema", "Auto-discovering from Postgres...")
        try:
            schema = discover_from_postgres(settings.postgres_url)
            log.success(
                "schema",
                f"Found {len(schema.tables)} tables: {schema.table_names()}"
            )
        except Exception as e:
            log.error("schema", f"Discovery failed: {e}")
            raise

    db.set_allowed_tables(schema.table_names())

    # ── Step 1: Read dashboard ───────────────────────────────────
    try:
        reading = reader_agent.run(image_path, log=log)
    except Exception as e:
        log.error("reader", f"Failed: {e}")
        raise

    # ── Step 2: Reason ───────────────────────────────────────────
    try:
        reasoning = reasoning_agent.run(reading, log=log)
    except Exception as e:
        log.error("reasoning", f"Failed: {e}")
        raise

    # ── Step 3: Diagnose ─────────────────────────────────────────
    bundles = []
    if reasoning.overall_severity in ("CRITICAL", "WARNING"):
        try:
            bundles = diagnosis_agent.run(reasoning, schema, log=log)
        except Exception as e:
            log.error("diagnosis", f"Failed: {e}")
            # Don't raise — continue to narrator with empty bundles
    else:
        log.info("diagnosis", "All normal — skipping Postgres queries")

    # ── Step 4: Narrate ──────────────────────────────────────────
    try:
        briefing = narrator_agent.run(reading, reasoning, bundles, log=log)
    except Exception as e:
        log.error("narrator", f"Failed: {e}")
        raise

    # ── Step 5: Deliver ──────────────────────────────────────────
    log.stage_start("delivery")

    # Save HTML briefing to disk
    os.makedirs("db", exist_ok=True)
    html_path = f"db/briefing_{run_id}.html"
    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(briefing.briefing_html)
        log.success("delivery", f"HTML saved: {html_path}")
    except Exception as e:
        log.error("delivery", f"HTML save failed: {e}")

    # Email
    try:
        email_ok = email_sender.send_briefing(
            briefing_text=briefing.briefing_text,
            briefing_html=briefing.briefing_html,
            subject=(
                f"Metric Watchdog — {briefing.overall_severity} — "
                f"{datetime.now().strftime('%d %b %Y')}"
            ),
        )
        log.info("delivery", f"Email: {'sent' if email_ok else 'disabled/failed'}")
    except Exception as e:
        log.error("delivery", f"Email error: {e}")

    # Slack
    try:
        slack_ok = slack_sender.send_briefing(
            briefing_text=briefing.briefing_text,
            severity=briefing.overall_severity,
        )
        log.info("delivery", f"Slack: {'sent' if slack_ok else 'disabled/failed'}")
    except Exception as e:
        log.error("delivery", f"Slack error: {e}")

    duration = time.time() - start
    log.stage_end("delivery", int(duration * 1000))

    # ── Build result ─────────────────────────────────────────────
    result = RunResult(
        run_id=run_id,
        date=datetime.now().isoformat(),
        dashboard_reading=reading,
        reasoning=reasoning,
        evidence_bundles=bundles,
        briefing=briefing,
        duration_seconds=duration,
        status="success",
    )

    # ── Save to history ──────────────────────────────────────────
    try:
        init_db()
        save_run(result)
        log.success("history", f"Run saved: {run_id}")
    except Exception as e:
        log.error("history", f"Save failed: {e}")

    log.pipeline_end(briefing.overall_severity, duration)

    # ── Print summary ────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  PIPELINE COMPLETE")
    print(f"  Run ID:      {run_id}")
    print(f"  Severity:    {briefing.overall_severity}")
    print(f"  Duration:    {duration:.1f}s")
    print(f"  Metrics:     {len(reading.metrics)}")
    print(f"  Proven:      {sum(len(b.proven) for b in bundles)}")
    print(f"  Unresolved:  {sum(len(b.unresolvable) for b in bundles)}")
    print(f"  Log:         logs/watchdog_{datetime.now().strftime('%Y%m%d')}.log")
    print(f"  HTML:        {html_path}")
    print(f"{'='*50}\n")

    return result