# agents/orchestrator.py

import time
from datetime import datetime
from core.models import RunResult
from core.schema import SchemaContext, discover_from_postgres
from core import db
from agents import reader_agent, reasoning_agent, diagnosis_agent, narrator_agent
from delivery import email_sender, slack_sender
from config.settings import settings


def run_pipeline(
    image_path: str,
    schema: SchemaContext | None = None,
) -> RunResult:
    run_id = f"watchdog_{datetime.now().strftime('%Y%m%d_%H%M')}"
    print(f"\n{'='*50}")
    print(f"  METRIC WATCHDOG — Run {run_id}")
    print(f"{'='*50}")

    start = time.time()

    # Load schema
    if schema is None:
        print("  [schema] Auto-discovering from Postgres...")
        schema = discover_from_postgres(settings.postgres_url)
        print(f"  [schema] Found {len(schema.tables)} tables: "
              f"{schema.table_names()}")

    db.set_allowed_tables(schema.table_names())

    # Step 1 — Read
    reading = reader_agent.run(image_path)

    # Step 2 — Reason
    reasoning = reasoning_agent.run(reading)

    # Step 3 — Diagnose
    bundles = []
    if reasoning.overall_severity in ("CRITICAL", "WARNING"):
        bundles = diagnosis_agent.run(reasoning, schema)
    else:
        print("  [diagnosis] All normal — skipping Postgres queries")
        bundles = []

    # Step 4 — Narrate
    briefing = narrator_agent.run(reading, reasoning, bundles)

    # Step 5 — Deliver
    print(f"\n  [delivery] Severity: {briefing.overall_severity}")
    print(f"\n{briefing.briefing_text}")

    # Save HTML briefing to disk
    html_path = f"db/briefing_{run_id}.html"
    import os
    os.makedirs("db", exist_ok=True)
    with open(html_path, "w") as f:
        f.write(briefing.briefing_html)
    print(f"  [delivery] HTML saved: {html_path}")

    # Email
    email_sender.send_briefing(
        briefing_text=briefing.briefing_text,
        briefing_html=briefing.briefing_html,
        subject=f"Metric Watchdog — {briefing.overall_severity} — "
                f"{datetime.now().strftime('%d %b %Y')}",
    )

    # Slack
    slack_sender.send_briefing(
        briefing_text=briefing.briefing_text,
        severity=briefing.overall_severity,
    )

    duration = time.time() - start

    print(f"\n{'='*50}")
    print(f"  PIPELINE COMPLETE")
    print(f"  Severity:    {briefing.overall_severity}")
    print(f"  Duration:    {duration:.1f}s")
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