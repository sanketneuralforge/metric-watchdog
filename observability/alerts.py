# observability/alerts.py

"""
Alert rules for Metric Watchdog.
Fires when production metrics cross thresholds.
"""

from dataclasses import dataclass
from observability.metrics import get_production_metrics


@dataclass
class Alert:
    level: str          # "critical" | "warning" | "info"
    rule: str           # rule name
    message: str        # human-readable message
    value: float        # current value that triggered alert
    threshold: float    # threshold that was crossed


def evaluate_alert_rules(days: int = 7) -> list[Alert]:
    """
    Evaluate all alert rules against current metrics.
    Returns list of active alerts.
    """
    metrics = get_production_metrics(days=days)
    alerts = []

    # Rule 1 — Completion rate below threshold
    completion = metrics["completion_rate_pct"]
    if completion < 70 and metrics["total_runs"] > 0:
        alerts.append(Alert(
            level="critical",
            rule="low_completion_rate",
            message=f"Completion rate {completion:.0f}% is below 70% threshold",
            value=completion,
            threshold=70.0,
        ))
    elif completion < 85 and metrics["total_runs"] > 0:
        alerts.append(Alert(
            level="warning",
            rule="low_completion_rate",
            message=f"Completion rate {completion:.0f}% is below 85% threshold",
            value=completion,
            threshold=85.0,
        ))

    # Rule 2 — High cost per run
    if metrics["total_runs"] > 0:
        cost_per_run = metrics["total_cost_usd"] / metrics["total_runs"]
        if cost_per_run > 0.10:
            alerts.append(Alert(
                level="warning",
                rule="high_cost_per_run",
                message=f"Average cost ${cost_per_run:.4f}/run exceeds $0.10 threshold",
                value=cost_per_run,
                threshold=0.10,
            ))

    # Rule 3 — Stage error rate
    for stage_err in metrics["stage_errors"]:
        stage = stage_err["stage"]
        errors = stage_err["errors"]
        if errors >= 3:
            alerts.append(Alert(
                level="warning",
                rule=f"stage_errors_{stage}",
                message=f"Stage '{stage}' has {errors} errors in last {days} days",
                value=errors,
                threshold=3,
            ))

    # Rule 4 — No runs in last 24 hours
    if metrics["total_runs"] == 0:
        alerts.append(Alert(
            level="warning",
            rule="no_recent_runs",
            message="No pipeline runs in the last 7 days",
            value=0,
            threshold=1,
        ))

    return alerts