# agents/reasoning_agent.py

import json
import time
from core.models import DashboardReading, ReasoningOutput, InvestigationGap
from core.llm import call_llm, parse_json_response
from core.run_logger import RunLog

REASONING_PROMPT = """
You are a senior data analyst reviewing a morning dashboard briefing.

You have been given a structured reading of a business dashboard.
Your job: reason through what you see, identify what's concerning,
spot co-moving metrics, and identify what's MISSING that would help
explain the movements.

RULES:
1. Only reference metrics that are in the dashboard reading provided.
2. Identify co-moving metrics — pairs that moved in the same window.
3. For each concerning movement, identify what decomposition or
   segmentation would explain it — even if that data is not in the dashboard.
4. Be explicit about severity: CRITICAL (needs immediate attention),
   WARNING (worth investigating today), NORMAL (no action needed).
5. Generate at least ONE gap per concerning metric.
6. Use the EXACT metric name in gap's metric_name field.

Return ONLY valid JSON — no markdown, no preamble:
{
  "concerning_metrics": ["metric names that moved significantly"],
  "co_moving_pairs": [["metric_a", "metric_b"]],
  "narrative": "2-3 sentence summary of what you see",
  "overall_severity": "CRITICAL | WARNING | NORMAL",
  "gaps": [
    {
      "question": "specific question dashboard cannot answer",
      "metric_name": "EXACT metric name from concerning_metrics list",
      "suggested_table": "orders | sessions | refunds | campaign_calendar",
      "suggested_query_type": "decomposition | segmentation | trend",
      "priority": "HIGH | MEDIUM | LOW",
      "suggested_next_step": "what analyst should do if we cannot check"
    }
  ]
}
"""


def run(reading: DashboardReading, log: RunLog | None = None) -> ReasoningOutput:
    start = time.time()
    if log:
        log.stage_start("reasoning")
        log.info("reasoning", f"Reasoning over {len(reading.metrics)} metrics")

    print(f"  [reasoning] Reasoning over {len(reading.metrics)} metrics...")

    metrics_text = "\n".join([
        f"- {m.name}: {m.value} {m.unit} "
        f"({m.direction}, change: {m.change_pct or 'unknown'}, "
        f"confidence: {m.confidence})"
        for m in reading.metrics
    ])

    charts_text = "\n".join([
        str(c) if not isinstance(c, str) else c
        for c in reading.charts_described
    ])

    user_message = f"""
Dashboard: {reading.dashboard_title}
Period: {reading.time_period}

Metrics observed:
{metrics_text}

Charts visible:
{charts_text}

Notes: {reading.reading_notes}

Reason through this dashboard and identify what needs investigation.
"""

    raw = call_llm(
        system_prompt=REASONING_PROMPT,
        user_message=user_message,
    )

    try:
        data = parse_json_response(raw)
    except Exception as e:
        if log:
            log.error("reasoning", f"Parse failed: {e}")
        data = {
            "concerning_metrics": [],
            "co_moving_pairs": [],
            "narrative": "Reasoning failed — manual review required",
            "overall_severity": "WARNING",
            "gaps": [],
        }

    gaps = [
        InvestigationGap(
            question=g["question"],
            metric_name=g["metric_name"],
            suggested_table=g["suggested_table"],
            suggested_query_type=g["suggested_query_type"],
            priority=g["priority"],
            suggested_next_step=g["suggested_next_step"],
        )
        for g in data.get("gaps", [])
    ]

    result = ReasoningOutput(
        concerning_metrics=data.get("concerning_metrics", []),
        co_moving_pairs=[tuple(p) for p in data.get("co_moving_pairs", [])],
        narrative=data.get("narrative", ""),
        gaps=gaps,
        overall_severity=data.get("overall_severity", "NORMAL"),
    )

    duration_ms = int((time.time() - start) * 1000)

    if log:
        log.info("reasoning", f"Severity: {result.overall_severity}")
        log.info("reasoning", f"Concerning: {result.concerning_metrics}")
        log.info("reasoning", f"Narrative: {result.narrative}")
        log.info("reasoning", f"Gaps generated: {len(result.gaps)}")
        for g in result.gaps:
            log.info("reasoning", f"  → [{g.priority}] {g.question[:80]}")
        log.stage_end("reasoning", duration_ms)

    print(f"  [reasoning] {len(result.concerning_metrics)} concerning, "
          f"{len(result.gaps)} gaps to investigate")
    return result