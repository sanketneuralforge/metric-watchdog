# tests/evals/fixtures.py

"""
Shared test fixtures for all evals.
Uses pre-built objects instead of running the full pipeline
so tests are fast and don't consume LLM quota unnecessarily.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.models import (
    DashboardReading, MetricObservation,
    ReasoningOutput, InvestigationGap,
    EvidenceBundle, Evidence, DiagnosisResult,
    BriefingDocument, BriefingSection,
)
from core.schema import SchemaContext, TableSchema


def get_test_reading_with_anomalies() -> DashboardReading:
    """Dashboard reading with clear anomalies — should trigger CRITICAL."""
    return DashboardReading(
        dashboard_title="E-commerce Daily Dashboard",
        time_period="Last 14 days",
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
        ],
        charts_described=[
            "Revenue line chart showing sharp drop in last 2 days",
            "Conversion rate line chart showing sharp drop",
            "Sessions relatively flat",
            "Orders bar chart declining",
        ],
        reading_notes="Clear anomaly in last 2 days across revenue and conversion",
        image_path="test_dashboard.png",
    )


def get_test_reading_normal() -> DashboardReading:
    """Dashboard reading with no anomalies — should trigger NORMAL."""
    return DashboardReading(
        dashboard_title="E-commerce Daily Dashboard",
        time_period="Last 14 days",
        metrics=[
            MetricObservation(
                name="Daily Revenue ($)",
                value="$68,400",
                unit="$",
                direction="flat",
                comparison="vs 7-day avg $67,200",
                change_value="+$1,200",
                change_pct="+1.8%",
                confidence="HIGH",
            ),
            MetricObservation(
                name="Conversion Rate (%)",
                value="3.1%",
                unit="%",
                direction="flat",
                comparison="vs 7-day avg 3.2%",
                change_value="-0.1pp",
                change_pct="-3.1%",
                confidence="HIGH",
            ),
        ],
        charts_described=["Revenue stable", "Conversion stable"],
        reading_notes="No significant movements",
        image_path="test_dashboard.png",
    )


def get_test_reasoning_critical() -> ReasoningOutput:
    """Pre-built reasoning output with CRITICAL severity."""
    return ReasoningOutput(
        concerning_metrics=["Daily Revenue ($)", "Conversion Rate (%)"],
        co_moving_pairs=[("Daily Revenue ($)", "Conversion Rate (%)")],
        narrative=(
            "Revenue dropped 39.8% driven by a 34.4% conversion rate collapse. "
            "Sessions flat so traffic is not the issue."
        ),
        gaps=[
            InvestigationGap(
                question="Which product category is driving the revenue drop?",
                metric_name="Daily Revenue ($)",
                suggested_table="orders",
                suggested_query_type="decomposition",
                priority="HIGH",
                suggested_next_step="Check orders table grouped by category",
            ),
            InvestigationGap(
                question="Is the conversion drop on mobile or desktop?",
                metric_name="Conversion Rate (%)",
                suggested_table="sessions",
                suggested_query_type="segmentation",
                priority="HIGH",
                suggested_next_step="Check sessions by device_type",
            ),
        ],
        overall_severity="CRITICAL",
    )


def get_test_schema() -> SchemaContext:
    """Test schema matching the synthetic e-commerce database."""
    return SchemaContext(
        tables=[
            TableSchema(
                name="orders",
                columns=[
                    "order_id integer", "created_at timestamp",
                    "customer_id integer", "category varchar",
                    "channel varchar", "device_type varchar",
                    "revenue decimal", "status varchar",
                ],
            ),
            TableSchema(
                name="sessions",
                columns=[
                    "session_id integer", "created_at timestamp",
                    "customer_id integer", "device_type varchar",
                    "channel varchar", "converted boolean",
                    "bounced boolean", "duration_seconds integer",
                ],
            ),
            TableSchema(
                name="refunds",
                columns=[
                    "refund_id integer", "order_id integer",
                    "created_at timestamp", "reason varchar",
                    "amount decimal",
                ],
            ),
            TableSchema(
                name="campaign_calendar",
                columns=[
                    "campaign_id integer", "campaign_name varchar",
                    "start_date date", "end_date date",
                    "channel varchar",
                ],
            ),
        ],
        source="manual",
    )


def get_populated_evidence_bundle() -> EvidenceBundle:
    """Evidence bundle with both proven and unresolvable claims."""
    bundle = EvidenceBundle(
        metric_name="Daily Revenue ($)",
        severity="CRITICAL",
    )
    bundle.proven.append(Evidence(
        claim="Electronics category revenue dropped 35% in last 2 days",
        claim_type="proven",
        confidence="HIGH",
        is_verified=True,
        source="sql:orders",
        source_detail="SELECT category, SUM(revenue) FROM orders GROUP BY category",
        row_count=1240,
    ))
    bundle.unresolvable.append(DiagnosisResult(
        gap=InvestigationGap(
            question="Did a marketing campaign run this week?",
            metric_name="Daily Revenue ($)",
            suggested_table="campaign_calendar",
            suggested_query_type="trend",
            priority="MEDIUM",
            suggested_next_step="Check campaign_calendar for active campaigns",
        ),
        resolved=False,
        sql_executed="SELECT * FROM campaign_calendar WHERE end_date >= NOW() - INTERVAL '7 days'",
        evidence=None,
        failure_reason="Query returned no results",
        suggested_next_step="Check campaign_calendar for active campaigns",
    ))
    return bundle