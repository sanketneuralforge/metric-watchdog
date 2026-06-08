# agents/orchestrator.py

import os
import time
from datetime import datetime

from core.models import RunResult, DashboardReading, ReasoningOutput
from core.schema import SchemaContext, discover_from_postgres
from core.run_logger import RunLog
from core.history_store import save_run, init_db
from core import db
from agents import reader_agent, reasoning_agent, diagnosis_agent, narrator_agent
from delivery import email_sender, slack_sender
from config.settings import settings
from guardrails.input_guard import (
    validate_dashboard_image,
    validate_postgres_url,
    check_vision_output_for_injection,
)
from guardrails.output_guard import (
    validate_briefing,
    scan_sql_for_dangerous_patterns,
)
from guardrails.degradation import (
    postgres_unavailable_briefing,
    vision_failed_briefing,
    partial_briefing_from_reading,
    check_pipeline_health,
)




def run_pipeline(
    image_path: str,
    schema: SchemaContext | None = None,
) -> RunResult:
    """
    Full pipeline: Read → Reason → Diagnose → Narrate → Deliver.
    Guardrails at every stage — degrades gracefully on failure.
    Logs every stage to plain text log file.
    Saves run to history store.
    """

    # ── Idempotency check ────────────────────────────────────────
    from core.idempotency import is_duplicate_run
    if is_duplicate_run(image_path):
        log.warning("preflight",
                    "Duplicate run detected — already ran for this "
                    "dashboard today. Skipping.")
        print("  ⚠ Duplicate run detected — skipping.")
        # Return early without running pipeline
        from core.history_store import get_recent_runs
        runs = get_recent_runs(limit=1)
        if runs:
            print(f"  Last run: {runs[0]['run_id']} — {runs[0]['severity']}")
        return None

    run_id = f"watchdog_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # ── Initialize logger ────────────────────────────────────────
    log = RunLog(run_id)
    log.pipeline_start(image_path)
    start = time.time()

    # ── Pre-flight health check ──────────────────────────────────
    health_warnings = check_pipeline_health(settings)
    for w in health_warnings:
        log.warning("preflight", w)
        print(f"  ⚠ {w}")

    # ── Ring 1: Validate image ───────────────────────────────────
    img_validation = validate_dashboard_image(image_path)
    if not img_validation.is_valid:
        log.error("reader", f"Input validation failed: {img_validation.error}")
        briefing = vision_failed_briefing(img_validation.error)
        _deliver(briefing, log)
        return _failed_result(run_id, image_path, briefing, time.time() - start)

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
            log.error("schema", f"Postgres unreachable: {e}")
            briefing = postgres_unavailable_briefing(str(e))
            _deliver(briefing, log)
            return _failed_result(run_id, image_path, briefing, time.time() - start)
    else:
        log.info("schema", f"Using provided schema: {schema.table_names()}")

    # Ring 1: Validate Postgres URL
    pg_validation = validate_postgres_url(settings.postgres_url)
    if not pg_validation.is_valid:
        log.error("schema", pg_validation.error)

    db.set_allowed_tables(schema.table_names())

    # ── Step 1: Read dashboard ───────────────────────────────────
    try:
        reading = reader_agent.run(image_path, log=log)
    except Exception as e:
        log.error("reader", f"Failed: {e}")
        briefing = vision_failed_briefing(str(e))
        _deliver(briefing, log)
        return _failed_result(run_id, image_path, briefing, time.time() - start)

    # Ring 2: Check vision output for injection attempts
    vision_text = " ".join([m.name + " " + m.value for m in reading.metrics])
    injection_check = check_vision_output_for_injection(vision_text)
    if not injection_check.is_valid:
        log.error("reader", f"Injection detected: {injection_check.error}")
        briefing = vision_failed_briefing(injection_check.error)
        _deliver(briefing, log)
        return _failed_result(run_id, image_path, briefing, time.time() - start)

    # ── Step 2: Reason ───────────────────────────────────────────
    try:
        reasoning = reasoning_agent.run(reading, log=log)
    except Exception as e:
        log.error("reasoning", f"Failed: {e}")
        # Degraded — deliver partial briefing from reading alone
        briefing = partial_briefing_from_reading(
            reading,
            ReasoningOutput(
                concerning_metrics=[],
                co_moving_pairs=[],
                narrative="Reasoning failed — manual review required",
                gaps=[],
                overall_severity="WARNING",
            ),
            str(e),
        )
        _deliver(briefing, log)
        return _failed_result(run_id, image_path, briefing, time.time() - start)

    # ── Step 3: Diagnose ─────────────────────────────────────────
    bundles = []
    if reasoning.overall_severity in ("CRITICAL", "WARNING"):
        try:
            bundles = diagnosis_agent.run(reasoning, schema, log=log)
        except Exception as e:
            log.error("diagnosis", f"Failed: {e}")
            # Don't raise — continue to narrator with empty bundles
            # partial_briefing will flag all claims as unverified
    else:
        log.info("diagnosis", "All normal — skipping Postgres queries")

    # ── Step 4: Narrate ──────────────────────────────────────────
    try:
        briefing = narrator_agent.run(reading, reasoning, bundles, log=log)
    except Exception as e:
        log.error("narrator", f"Failed: {e}")
        briefing = partial_briefing_from_reading(reading, reasoning, str(e))

    # ── Ring 4: Validate output ──────────────────────────────────
    output_validation = validate_briefing(
        briefing,
        bundles,
        allowed_tables=db._allowed_tables,
    )
    if output_validation.violations:
        for v in output_validation.violations:
            log.error("output_guard", f"Violation: {v}")
    for w in output_validation.warnings:
        log.warning("output_guard", f"Warning: {w}")

    if not output_validation.is_valid:
        log.error("output_guard",
                  f"{len(output_validation.violations)} violations — "
                  f"briefing may be incomplete")

    # ── Step 5: Deliver ──────────────────────────────────────────
    _deliver(briefing, log)

    # Save HTML briefing
    os.makedirs("db", exist_ok=True)
    html_path = f"db/briefing_{run_id}.html"
    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(briefing.briefing_html)
        log.success("delivery", f"HTML saved: {html_path}")
    except Exception as e:
        log.error("delivery", f"HTML save failed: {e}")

    duration = time.time() - start

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

    # ── Token usage estimate ─────────────────────────────────────
    from core.token_budget import TokenUsage, estimate_tokens
    usage = TokenUsage(run_id=run_id)
    # Rough estimates from pipeline stages
    usage.reasoning_input = estimate_tokens(str(reading.metrics))
    usage.reasoning_output = estimate_tokens(reasoning.narrative)
    usage.diagnosis_input = estimate_tokens(schema.to_prompt_block()) * len(reasoning.gaps)
    usage.diagnosis_output = estimate_tokens(str(bundles))
    usage.narrator_input = estimate_tokens(briefing.briefing_text)
    usage.narrator_output = estimate_tokens(briefing.briefing_text)

    cost = usage.estimated_cost_usd(settings.llm_provider)
    log.info("cost", f"Estimated tokens: {usage.total()} | "
                     f"Estimated cost: ${cost:.4f}")
    print(f"  Tokens:      ~{usage.total():,}")
    print(f"  Est. cost:   ${cost:.4f}")

    # ── Save to history ──────────────────────────────────────────
    try:
        init_db()
        save_run(result)
        log.success("history", f"Run saved: {run_id}")
    except Exception as e:
        log.error("history", f"Save failed: {e}")

    log.pipeline_end(briefing.overall_severity, duration)

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


def _deliver(briefing, log: RunLog):
    """Send briefing via email and Slack."""
    log.stage_start("delivery")
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

    try:
        slack_ok = slack_sender.send_briefing(
            briefing_text=briefing.briefing_text,
            severity=briefing.overall_severity,
        )
        log.info("delivery", f"Slack: {'sent' if slack_ok else 'disabled/failed'}")
    except Exception as e:
        log.error("delivery", f"Slack error: {e}")


def _failed_result(
    run_id: str,
    image_path: str,
    briefing,
    duration: float,
) -> RunResult:
    """Build a RunResult for a failed/degraded pipeline run."""
    return RunResult(
        run_id=run_id,
        date=datetime.now().isoformat(),
        dashboard_reading=DashboardReading(
            metrics=[],
            time_period="",
            dashboard_title="",
            charts_described=[],
            reading_notes="Pipeline failed",
            image_path=image_path,
        ),
        reasoning=ReasoningOutput(
            concerning_metrics=[],
            co_moving_pairs=[],
            narrative="",
            gaps=[],
            overall_severity="CRITICAL",
        ),
        evidence_bundles=[],
        briefing=briefing,
        duration_seconds=duration,
        status="failed",
    )