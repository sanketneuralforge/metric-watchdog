# agents/orchestrator.py

import time
from datetime import datetime
from core.models import RunResult
from core.schema import SchemaContext, discover_from_postgres
from core import db
from agents import reader_agent, reasoning_agent, diagnosis_agent
from config.settings import settings


def run_pipeline(
    image_path: str,
    schema: SchemaContext | None = None,
) -> RunResult:
    """
    Main pipeline entry point.

    schema: if None, auto-discovers from Postgres connection.
            Pass explicitly to use a custom schema.
    """
    run_id = f"watchdog_{datetime.now().strftime('%Y%m%d_%H%M')}"
    print(f"\n{'='*50}")
    print(f"  METRIC WATCHDOG — Run {run_id}")
    print(f"{'='*50}")

    start = time.time()

    # Load schema — auto-discover if not provided
    if schema is None:
        print("  [schema] Auto-discovering from Postgres...")
        schema = discover_from_postgres(settings.postgres_url)
        print(f"  [schema] Found {len(schema.tables)} tables: "
              f"{schema.table_names()}")

    # Register allowed tables with DB layer
    db.set_allowed_tables(schema.table_names())

    # Step 1 — Read dashboard
    reading = reader_agent.run(image_path)

    # Step 2 — Reason
    reasoning = reasoning_agent.run(reading)

    # Step 3 — Diagnose
    bundles = []
    if reasoning.overall_severity in ("CRITICAL", "WARNING"):
        bundles = diagnosis_agent.run(reasoning, schema)
    else:
        print("  [diagnosis] All normal — skipping Postgres queries")

    duration = time.time() - start

    print(f"\n{'='*50}")
    print(f"  PIPELINE COMPLETE")
    print(f"  Severity:    {reasoning.overall_severity}")
    print(f"  Concerning:  {reasoning.concerning_metrics}")
    print(f"  Narrative:   {reasoning.narrative}")
    for b in bundles:
        print(f"  {b.metric_name}: "
              f"{len(b.proven)} proven, "
              f"{len(b.unresolvable)} unresolvable")
    print(f"  Duration:    {duration:.1f}s")
    print(f"{'='*50}\n")

    return RunResult(
        run_id=run_id,
        date=datetime.now().isoformat(),
        dashboard_reading=reading,
        reasoning=reasoning,
        evidence_bundles=bundles,
        briefing_text="",
        briefing_html="",
        duration_seconds=duration,
        status="partial",
    )