# test_text_pipeline.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))


# test_text_pipeline.py — first 5 lines must be:

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
os.environ["LLM_PROVIDER"] = "groq"  # must be before settings import


from core.models import (
    DashboardReading, MetricObservation,
    ReasoningOutput, InvestigationGap
)
from core.schema import discover_from_postgres
from core import db
from agents import diagnosis_agent, narrator_agent
from config.settings import settings

print("\n" + "="*50)
print("  METRIC WATCHDOG — Text Pipeline Test")
print("="*50)

# ── Step 1: Manually provide what vision would have extracted ──
reading = DashboardReading(
    dashboard_title="E-commerce Daily Dashboard",
    time_period="Last 14 days (May 22 - June 4 2026)",
    metrics=[
        MetricObservation(
            name="Daily Revenue ($)",
            value="$41,200",
            unit="$",
            direction="down",
            comparison="vs 7-day avg $68,400",
            change_value="-$27,200",
            change_pct="-39.8%",
            confidence="HIGH",
        ),
        MetricObservation(
            name="Daily Orders",
            value="831",
            unit="count",
            direction="down",
            comparison="vs 7-day avg 1,043",
            change_value="-212",
            change_pct="-20.3%",
            confidence="HIGH",
        ),
        MetricObservation(
            name="Conversion Rate (%)",
            value="2.1%",
            unit="%",
            direction="down",
            comparison="vs 7-day avg 3.2%",
            change_value="-1.1pp",
            change_pct="-34.4%",
            confidence="HIGH",
        ),
        MetricObservation(
            name="Daily Sessions",
            value="9,012",
            unit="count",
            direction="flat",
            comparison="vs 7-day avg 9,800",
            change_value="-788",
            change_pct="-8.0%",
            confidence="HIGH",
        ),
    ],
    charts_described=[
        "Revenue line chart showing sharp drop in last 2 days",
        "Orders bar chart showing decline last 2 days",
        "Sessions line chart relatively flat",
        "Conversion rate line chart showing sharp drop last 2 days",
    ],
    reading_notes="Values for last 2 days clearly below trend",
    image_path="test_dashboard.png",
)

print(f"\n  Dashboard: {reading.dashboard_title}")
print(f"  Period: {reading.time_period}")
print(f"  Metrics: {len(reading.metrics)}")

# ── Step 2: Manually provide what reasoning would have produced ──
reasoning = ReasoningOutput(
    concerning_metrics=[
        "Daily Revenue ($)",
        "Conversion Rate (%)",
        "Daily Orders",
    ],
    co_moving_pairs=[
        ("Daily Revenue ($)", "Conversion Rate (%)"),
        ("Daily Revenue ($)", "Daily Orders"),
    ],
    narrative=(
        "Revenue dropped 39.8% in the last 2 days driven by a 34.4% "
        "conversion rate collapse. Sessions remained relatively flat "
        "(-8%) meaning traffic is not the issue — something in the "
        "checkout funnel or product mix changed. Orders dropped 20% "
        "which is proportionally less than revenue, suggesting the "
        "remaining orders may have lower AOV."
    ),
    gaps=[
        InvestigationGap(
            question="Which product category is driving the revenue drop — is it concentrated in one category or broad?",
            metric_name="Daily Revenue ($)",
            suggested_table="orders",
            suggested_query_type="decomposition",
            priority="HIGH",
            suggested_next_step="Check orders table grouped by category for last 7 days vs prior 7 days",
        ),
        InvestigationGap(
            question="Is the conversion rate drop concentrated on mobile or desktop?",
            metric_name="Conversion Rate (%)",
            suggested_table="sessions",
            suggested_query_type="segmentation",
            priority="HIGH",
            suggested_next_step="Check sessions table grouped by device_type for last 7 days",
        ),
        InvestigationGap(
            question="Did the refund rate spike in the last 2 days suggesting product quality issues?",
            metric_name="Daily Revenue ($)",
            suggested_table="refunds",
            suggested_query_type="trend",
            priority="MEDIUM",
            suggested_next_step="Check refunds table by date and reason for last 14 days",
        ),
        InvestigationGap(
            question="Is there an active campaign that could explain the traffic pattern?",
            metric_name="Daily Sessions",
            suggested_table="campaign_calendar",
            suggested_query_type="trend",
            priority="MEDIUM",
            suggested_next_step="Check campaign_calendar for active campaigns this week",
        ),
    ],
    overall_severity="CRITICAL",
)

print(f"\n  Severity: {reasoning.overall_severity}")
print(f"  Concerning: {reasoning.concerning_metrics}")
print(f"  Gaps: {len(reasoning.gaps)}")

# ── Step 3: Auto-discover schema and run diagnosis ─────────────
print("\n  [schema] Auto-discovering...")
schema = discover_from_postgres(settings.postgres_url)
db.set_allowed_tables(schema.table_names())
print(f"  [schema] {len(schema.tables)} tables found")

print("\n  [diagnosis] Running SQL investigation...")
bundles = diagnosis_agent.run(reasoning, schema)

# ── Step 4: Narrate ────────────────────────────────────────────
print("\n  [narrator] Writing sourced briefing...")
briefing = narrator_agent.run(reading, reasoning, bundles)

# ── Print full briefing ────────────────────────────────────────
print("\n" + "="*50)
print("  MORNING BRIEFING")
print("="*50)
print(briefing.briefing_text)

# Save HTML
import os
os.makedirs("db", exist_ok=True)
html_path = "db/test_briefing.html"
with open(html_path, "w") as f:
    f.write(briefing.briefing_html)
print(f"\n  HTML saved: {html_path}")
print(f"  Open with: open {html_path}")