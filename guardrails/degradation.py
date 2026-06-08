# guardrails/degradation.py

"""
Ring 3 — Graceful degradation handlers.

When something fails the pipeline should:
1. Log the failure clearly
2. Continue with what it has (partial results)
3. Never crash silently
4. Always produce a deliverable — even if it's just an alert

Failure scenarios:
- Postgres unreachable
- Vision model timeout
- LLM rate limit
- Schema discovery fails
- Narrator LLM fails
"""

from datetime import datetime
from core.models import (
    DashboardReading, ReasoningOutput,
    EvidenceBundle, BriefingDocument, BriefingSection,
)


def postgres_unavailable_briefing(error: str) -> BriefingDocument:
    """
    Fallback briefing when Postgres is unreachable.
    Sends an alert so the analyst knows the diagnostic
    SQL step was skipped.
    """
    text = f"""🔴 METRIC WATCHDOG — {datetime.now().strftime('%A %d %B %Y, %H:%M')}
{'━'*50}

⚠️  DIAGNOSTIC UNAVAILABLE — DATABASE UNREACHABLE

Metric Watchdog could not connect to the database
to run diagnostic SQL queries.

Error: {error}

What this means:
- Dashboard was read successfully
- Metric movements were identified
- SQL investigation COULD NOT be completed
- This briefing contains NO proven claims

Recommended action:
1. Check Postgres connection: {error[:100]}
2. Verify POSTGRES_URL in .env
3. Re-run Metric Watchdog once database is available

Run ID: unavailable
"""
    html = f"""
<html><body style="font-family:Arial;padding:20px;background:#fff;">
<div style="background:#dc2626;color:white;padding:16px;border-radius:8px;">
    <h2>⚠️ Metric Watchdog — Database Unavailable</h2>
    <p>{datetime.now().strftime('%A %d %B %Y, %H:%M')}</p>
</div>
<div style="margin-top:16px;padding:16px;background:#fef2f2;
            border-left:4px solid #dc2626;border-radius:4px;">
    <p><strong>Postgres unreachable:</strong> {error}</p>
    <p>Diagnostic SQL could not run. No proven claims available.</p>
    <p><strong>Action:</strong> Check database connection and re-run.</p>
</div>
</body></html>"""

    return BriefingDocument(
        run_id=f"watchdog_degraded_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        date=datetime.now().strftime("%A %d %B %Y"),
        sections=[],
        overall_severity="CRITICAL",
        executive_summary="Database unavailable — diagnostic incomplete",
        recommended_actions=[{
            "action": "Check Postgres connection and re-run",
            "priority": "immediate",
            "effort": "15min",
        }],
        briefing_text=text,
        briefing_html=html,
    )


def vision_failed_briefing(error: str) -> BriefingDocument:
    """Fallback when vision model fails to read the dashboard."""
    text = f"""🟡 METRIC WATCHDOG — {datetime.now().strftime('%A %d %B %Y, %H:%M')}
{'━'*50}

⚠️  DASHBOARD READING FAILED

Metric Watchdog could not read the dashboard image.

Error: {error}

Recommended action:
1. Check that the dashboard image is a valid PNG or JPG
2. Ensure the image is at least 100KB
3. Try uploading a higher resolution screenshot
4. Re-run Metric Watchdog

"""
    return BriefingDocument(
        run_id=f"watchdog_degraded_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        date=datetime.now().strftime("%A %d %B %Y"),
        sections=[],
        overall_severity="WARNING",
        executive_summary="Vision model failed — could not read dashboard",
        recommended_actions=[{
            "action": "Re-upload dashboard image and retry",
            "priority": "today",
            "effort": "15min",
        }],
        briefing_text=text,
        briefing_html=f"<html><body><pre>{text}</pre></body></html>",
    )


def partial_briefing_from_reading(
    reading: DashboardReading,
    reasoning: ReasoningOutput,
    error: str,
) -> BriefingDocument:
    """
    Fallback briefing when diagnosis fails but reading and
    reasoning succeeded. Uses only dashboard observations —
    no SQL proven claims.
    """
    metrics_text = "\n".join([
        f"  • {m.name}: {m.value} ({m.direction})"
        for m in reading.metrics
    ])

    text = f"""🟡 METRIC WATCHDOG — {datetime.now().strftime('%A %d %B %Y, %H:%M')}
{'━'*50}

SEVERITY: {reasoning.overall_severity}
Note: SQL diagnosis unavailable — {error}

DASHBOARD OBSERVATIONS (unverified — from image only):
{metrics_text}

REASONING:
{reasoning.narrative}

⚠️  ALL CLAIMS BELOW ARE [UNVERIFIED] — NO SQL WAS EXECUTED

Concerning metrics: {', '.join(reasoning.concerning_metrics)}

Investigation gaps (could not check):
""" + "\n".join([
        f"  • {g.question}\n    → {g.suggested_next_step}"
        for g in reasoning.gaps
    ])

    return BriefingDocument(
        run_id=f"watchdog_partial_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        date=datetime.now().strftime("%A %d %B %Y"),
        sections=[],
        overall_severity=reasoning.overall_severity,
        executive_summary=f"Partial briefing — {reasoning.narrative}",
        recommended_actions=[{
            "action": g.suggested_next_step,
            "priority": "today",
            "effort": "15min",
        } for g in reasoning.gaps[:3]],
        briefing_text=text,
        briefing_html=f"<html><body><pre>{text}</pre></body></html>",
    )


def check_pipeline_health(settings) -> list[str]:
    """
    Pre-flight health check before running the pipeline.
    Returns list of warnings — empty means all clear.
    """
    warnings = []

    if not settings.groq_api_key and settings.llm_provider == "groq":
        warnings.append("GROQ_API_KEY not set — LLM calls will fail")

    if not settings.gemini_api_key and settings.vision_provider == "gemini":
        warnings.append("GEMINI_API_KEY not set — vision calls will fail")

    if not settings.postgres_url:
        warnings.append("POSTGRES_URL not set — SQL diagnosis will fail")

    return warnings