# agents/orchestrator.py

import time
from datetime import datetime
from core.models import RunResult
from core.schema import SchemaContext, discover_from_postgres
from core.run_logger import RunLog
from core import db
from agents import reader_agent, reasoning_agent, diagnosis_agent, narrator_agent
from delivery import email_sender, slack_sender
from config.settings import settings


def run_pipeline(
    image_path: str,
    schema: SchemaContext | None = None,
) -> RunResult:
    run_id = f"watchdog_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # ── Initialize run logger ────────────────────────────────────
    log = RunLog(run_id)
    log.pipeline_start(image_path)

    start = time.time()

    # Schema
    if schema is None:
        log.info("schema", "Auto-discovering from Postgres...")
        schema = discover_from_postgres(settings.postgres_url)
        log.success("schema", f"Found {len(schema.tables)} tables: {schema.table_names()}")

    db.set_allowed_tables(schema.table_names())

    # Step 1 — Read
    reading = reader_agent.run(image_path, log=log)

    # Step 2 — Reason
    reasoning = reasoning_agent.run(reading, log=log)

    # Step 3 — Diagnose
    bundles = []
    if reasoning.overall_severity in ("CRITICAL", "WARNING"):
        bundles = diagnosis_agent.run(reasoning, schema, log=log)
    else:
        log.info("diagnosis", "All normal — skipping Postgres queries")

    # Step 4 — Narrate
    briefing = narrator_agent.run(reading, reasoning, bundles, log=log)

    # Step 5 — Deliver
    log.stage_start("delivery")

    import os
    os.makedirs("db", exist_ok=True)
    html_path = f"db/briefing_{run_id}.html"
    with open(html_path, "w") as f:
        f.write(briefing.briefing_html)
    log.success("delivery", f"HTML saved: {html_path}")

    email_ok = email_sender.send_briefing(
        briefing_text=briefing.briefing_text,
        briefing_html=briefing.briefing_html,
        subject=f"Metric Watchdog — {briefing.overall_severity} — "
                f"{datetime.now().strftime('%d %b %Y')}",
    )
    log.info("delivery", f"Email: {'sent' if email_ok else 'disabled/failed'}")

    slack_ok = slack_sender.send_briefing(
        briefing_text=briefing.briefing_text,
        severity=briefing.overall_severity,
    )
    log.info("delivery", f"Slack: {'sent' if slack_ok else 'disabled/failed'}")

    duration = time.time() - start
    log.pipeline_end(briefing.overall_severity, duration)

    print(f"\n{'='*50}")
    print(f"  PIPELINE COMPLETE")
    print(f"  Severity:    {briefing.overall_severity}")
    print(f"  Duration:    {duration:.1f}s")
    print(f"  Log:         logs/watchdog_{datetime.now().strftime('%Y%m%d')}.log")
    print(f"  HTML:        {html_path}")
    print(f"{'='*50}\n")

    return RunResult(
        run_id=run_id,
        date=datetime.now().isoformat(),
        dashboard_reading=reading,
        reasoning=reasoning,
        evidence_bundles=bundles,
        briefing=briefing,
        duration_seconds=duration,
        status="success",
    )