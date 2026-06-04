# core/models.py

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MetricObservation:
    name: str
    value: str
    unit: str
    direction: str           # up | down | flat | unknown
    comparison: str
    change_value: str | None
    change_pct: str | None
    confidence: str          # HIGH | MEDIUM | LOW
    source: str = "dashboard"


@dataclass
class DashboardReading:
    metrics: list[MetricObservation]
    time_period: str
    dashboard_title: str
    charts_described: list[str]
    reading_notes: str
    image_path: str
    read_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )


@dataclass
class InvestigationGap:
    question: str
    metric_name: str
    suggested_table: str
    suggested_query_type: str    # decomposition | segmentation | trend
    priority: str                # HIGH | MEDIUM | LOW
    suggested_next_step: str     # what analyst should do manually


@dataclass
class ReasoningOutput:
    concerning_metrics: list[str]
    co_moving_pairs: list[tuple[str, str]]
    narrative: str
    gaps: list[InvestigationGap]
    overall_severity: str        # CRITICAL | WARNING | NORMAL


@dataclass
class Evidence:
    claim: str
    claim_type: str              # proven | inferred | hypothesised
    confidence: str              # HIGH | MEDIUM | LOW
    is_verified: bool
    source: str                  # "dashboard" | "sql:table_name"
    source_detail: str           # SQL or image observation
    row_count: int | None = None
    dashboard_url: str | None = None


@dataclass
class DiagnosisResult:
    gap: InvestigationGap
    resolved: bool
    sql_executed: str | None
    evidence: Evidence | None
    failure_reason: str | None
    suggested_next_step: str | None


@dataclass
class EvidenceBundle:
    metric_name: str
    severity: str
    proven: list[Evidence] = field(default_factory=list)
    inferred: list[Evidence] = field(default_factory=list)
    hypothesised: list[Evidence] = field(default_factory=list)
    unresolvable: list[DiagnosisResult] = field(default_factory=list)
    diagnostic_dashboard_path: str | None = None


@dataclass
class RunResult:
    run_id: str
    date: str
    dashboard_reading: DashboardReading
    reasoning: ReasoningOutput
    evidence_bundles: list[EvidenceBundle]
    briefing: "BriefingDocument | None" = None
    duration_seconds: float = 0.0
    status: str = "partial"


# Add to core/models.py

@dataclass
class BriefingSection:
    metric_name: str
    severity: str
    what_we_know: list[dict] = field(default_factory=list)
    what_we_inferred: list[dict] = field(default_factory=list)
    what_we_couldnt_check: list[dict] = field(default_factory=list)
    headline: str = ""


@dataclass
class BriefingDocument:
    run_id: str
    date: str
    sections: list[BriefingSection]
    overall_severity: str
    executive_summary: str
    recommended_actions: list[dict]
    briefing_text: str
    briefing_html: str