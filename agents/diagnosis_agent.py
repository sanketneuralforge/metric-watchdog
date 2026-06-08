# agents/diagnosis_agent.py

"""
Step 3 — Fills investigation gaps via Postgres.
For each gap identified by the reasoning agent:
  - Semantically matches gaps to metrics
  - Writes targeted SQL using the provided schema
  - Executes it safely
  - Builds Evidence objects from results
  - If query fails, logs it as unresolvable with next steps
"""

import json
from core.models import (
    ReasoningOutput, InvestigationGap,
    DiagnosisResult, Evidence, EvidenceBundle
)
from core.llm import call_llm, parse_json_response
from core.db import execute_query_safe

SQL_WRITER_PROMPT = """
You are a senior data analyst writing diagnostic SQL queries.

You will be given a specific investigation question and the EXACT
database schema available. You MUST only use tables and columns
that appear in the schema below. Never invent table or column names.

STRICT RULES:
1. ONLY use tables listed in the schema provided to you
2. ONLY use columns that exist in those tables
3. Only SELECT statements — no writes
4. Always filter WHERE created_at >= NOW() - INTERVAL '14 days'
5. For decomposition: GROUP BY one dimension at a time
6. For segmentation: use CASE WHEN or GROUP BY the segment column
7. If the question cannot be answered with the available schema,
   return an empty sql field and explain why in the explanation

Return ONLY valid JSON — no markdown, no preamble:
{
  "sql": "your SELECT query or empty string if not possible",
  "explanation": "what this query measures or why it cannot be written",
  "interpretation_guide": "if result shows X it means Y"
}
"""

EVIDENCE_BUILDER_PROMPT = """
You are a senior data analyst interpreting SQL query results.

You will be given:
1. The investigation question
2. The SQL query that was run
3. The query results as JSON

Build an evidence object from these results.
Only state what the data actually shows. Never speculate beyond the numbers.

RULES:
1. claim_type must always be "proven" — this came from actual data
2. confidence based on row count:
   HIGH = n > 1000, MEDIUM = 100-1000, LOW = n < 100
3. If results are empty, state that explicitly
4. Never invent numbers not present in the results
5. key_finding should be the single most actionable number

Return ONLY valid JSON — no markdown, no preamble:
{
  "claim": "specific factual claim from the data",
  "claim_type": "proven",
  "confidence": "HIGH | MEDIUM | LOW",
  "is_verified": true,
  "source": "sql:table_name",
  "source_detail": "brief description of what query measured",
  "row_count": 0,
  "key_finding": "single most important number from the results"
}
"""

GAP_MATCHING_PROMPT = """
You are matching investigation gaps to the metrics they relate to.

You will be given:
1. A list of metric names as they appear on the dashboard
2. A list of investigation gaps, each with a metric_name field

Your job: for each gap, find the best matching metric from the
dashboard list. Use semantic understanding — names will differ.

Examples of matches:
- gap "revenue" matches dashboard "Daily Revenue ($)"
- gap "conversion" matches dashboard "Conversion Rate (%)"
- gap "sessions" matches dashboard "Daily Sessions"
- gap "orders" matches dashboard "Daily Orders"
- gap "aov" matches dashboard "Average Order Value"

Return ONLY valid JSON — no markdown, no preamble:
{
  "matches": [
    {
      "gap_index": 0,
      "matched_metric": "exact metric name from dashboard list, or null if no match"
    }
  ]
}
"""


def run(
    reasoning: ReasoningOutput,
    schema: "SchemaContext",
    log: "RunLog | None" = None,
) -> list[EvidenceBundle]:
    """
    For each concerning metric, investigate its gaps via Postgres.
    Uses semantic matching to connect gaps to metrics regardless
    of naming differences between dashboards.
    """
    print(f"  [diagnosis] Investigating {len(reasoning.gaps)} gaps...")

    if not reasoning.gaps:
        return [
            EvidenceBundle(
                metric_name=m,
                severity=reasoning.overall_severity,
            )
            for m in reasoning.concerning_metrics
        ]

    # Semantically match gaps to dashboard metric names
    gap_to_metric = _match_gaps_to_metrics(
        reasoning.concerning_metrics,
        reasoning.gaps,
    )

    print(f"  [diagnosis] Gap matches: {gap_to_metric}")

    # Group gaps by matched metric
    gaps_by_metric: dict[str, list[InvestigationGap]] = {
        m: [] for m in reasoning.concerning_metrics
    }
    for i, gap in enumerate(reasoning.gaps):
        matched = gap_to_metric.get(i)
        if matched and matched in gaps_by_metric:
            gaps_by_metric[matched].append(gap)
        else:
            # No match — assign to first concerning metric as fallback
            if reasoning.concerning_metrics:
                fallback = reasoning.concerning_metrics[0]
                gaps_by_metric[fallback].append(gap)
                print(f"  [diagnosis] Gap {i} unmatched — assigned to {fallback}")

    # Investigate each metric
    bundles = []
    for metric_name in reasoning.concerning_metrics:
        gaps = gaps_by_metric.get(metric_name, [])
        print(f"  [diagnosis] {metric_name}: {len(gaps)} gap(s)")
        bundle = _investigate_metric(metric_name, gaps, reasoning, schema, log=log)
        bundles.append(bundle)

    print(f"  [diagnosis] Built {len(bundles)} evidence bundles")
    return bundles


def _match_gaps_to_metrics(
    metric_names: list[str],
    gaps: list[InvestigationGap],
) -> dict[int, str]:
    """
    Semantically match each gap to the most relevant dashboard metric.
    Returns dict of gap_index -> matched_metric_name.
    """
    if not metric_names or not gaps:
        return {}

    user_message = f"""
Dashboard metric names:
{json.dumps(metric_names, indent=2)}

Investigation gaps to match:
{json.dumps([
    {
        "index": i,
        "metric_name": g.metric_name,
        "question": g.question[:100],
    }
    for i, g in enumerate(gaps)
], indent=2)}

Match each gap index to the most semantically similar dashboard metric name.
"""

    try:
        raw = call_llm(
            system_prompt=GAP_MATCHING_PROMPT,
            user_message=user_message,
        )
        data = parse_json_response(raw)
        return {
            m["gap_index"]: m["matched_metric"]
            for m in data.get("matches", [])
            if m.get("matched_metric")
        }
    except Exception as e:
        print(f"  [diagnosis] Gap matching failed: {e} — using fallback")
        return {i: metric_names[0] for i in range(len(gaps))}


def _investigate_metric(
    metric_name: str,
    gaps: list[InvestigationGap],
    reasoning: ReasoningOutput,
    schema: "SchemaContext",
    log: "RunLog | None" = None,
) -> EvidenceBundle:
    """Investigate one metric — run SQL for each of its gaps."""
    bundle = EvidenceBundle(
        metric_name=metric_name,
        severity=reasoning.overall_severity,
    )

    if not gaps:
        return bundle

    for gap in gaps:
        result = _investigate_gap(gap, schema, log=log)
        if result.resolved and result.evidence:
            bundle.proven.append(result.evidence)
        else:
            bundle.unresolvable.append(result)

    return bundle


def _investigate_gap(
    gap: InvestigationGap,
    schema: "SchemaContext",
    log: "RunLog | None" = None,
) -> DiagnosisResult:
    import time
    start = time.time()

    print(f"    [diagnosis] Investigating: {gap.question[:60]}...")
    if log:
        log.info("diagnosis", f"Investigating: {gap.question}")

    # Write SQL
    sql_response = _write_sql(gap, schema, log=log)
    if not sql_response:
        if log:
            log.error("diagnosis:sql", f"SQL generation failed for: {gap.question[:60]}")
        return DiagnosisResult(
            gap=gap, resolved=False, sql_executed=None,
            evidence=None, failure_reason="SQL generation failed",
            suggested_next_step=gap.suggested_next_step,
        )

    sql = sql_response.get("sql", "").strip()
    if not sql:
        if log:
            log.error("diagnosis:sql", "LLM returned empty SQL")
        return DiagnosisResult(
            gap=gap, resolved=False, sql_executed=None,
            evidence=None, failure_reason="Empty SQL returned",
            suggested_next_step=gap.suggested_next_step,
        )

    # Log the full SQL before executing
    if log:
        log.info("diagnosis:sql", f"Gap: {gap.question[:80]}")
        log.logger.debug(f"[diagnosis:sql] Full query:\n{sql}")

    # Execute
    results, error = execute_query_safe(sql)

    if error:
        if log:
            log.error("diagnosis:sql", f"FAILED: {error}")
            log.error("diagnosis:sql", f"Query was:\n{sql}")
        print(f"    [diagnosis] Query failed: {error[:80]}")
        return DiagnosisResult(
            gap=gap, resolved=False, sql_executed=sql,
            evidence=None, failure_reason=f"Query failed: {error}",
            suggested_next_step=gap.suggested_next_step,
        )

    if not results:
        if log:
            log.warning("diagnosis:sql", f"Query returned 0 rows — {gap.question[:60]}")
        return DiagnosisResult(
            gap=gap, resolved=False, sql_executed=sql,
            evidence=None, failure_reason="No results returned",
            suggested_next_step=gap.suggested_next_step,
        )

    if log:
        log.success("diagnosis:sql", f"{len(results)} rows returned")

    evidence = _build_evidence(gap, sql, results)
    return DiagnosisResult(
        gap=gap, resolved=True, sql_executed=sql,
        evidence=evidence, failure_reason=None,
        suggested_next_step=None,
    )

def _write_sql(
    gap: InvestigationGap,
    schema: "SchemaContext",
    log: "RunLog | None" = None,
) -> dict | None:
    user_message = f"""
Investigation question: {gap.question}
Metric concerned: {gap.metric_name}
Query type: {gap.suggested_query_type}

{schema.to_prompt_block()}

Write SQL using ONLY the tables and columns listed above.
Focus on last 7-14 days.
"""
    try:
        raw = call_llm(
            system_prompt=SQL_WRITER_PROMPT,
            user_message=user_message,
        )
        result = parse_json_response(raw)
        if log:
            log.info("diagnosis:sql", f"SQL written: {result.get('explanation', '')[:80]}")
        return result
    except Exception as e:
        print(f"    [diagnosis] SQL write failed: {e}")
        if log:
            log.error("diagnosis:sql", f"SQL write failed: {e}")
        return None


def _build_evidence(
    gap: InvestigationGap,
    sql: str,
    results: list[dict],
) -> Evidence:
    """Interpret query results and build a typed Evidence object."""
    sample = results[:20]
    row_count = len(results)

    user_message = f"""
Investigation question: {gap.question}

SQL that was executed:
{sql}

Query results ({row_count} total rows, showing first {len(sample)}):
{json.dumps(sample, indent=2, default=str)}

Build an evidence object from these results.
State only what the data shows. Be specific about numbers.
"""
    try:
        raw = call_llm(
            system_prompt=EVIDENCE_BUILDER_PROMPT,
            user_message=user_message,
        )
        data = parse_json_response(raw)
        return Evidence(
            claim=data.get("claim", ""),
            claim_type="proven",
            confidence=data.get("confidence", "MEDIUM"),
            is_verified=True,
            source=f"sql:{gap.suggested_table}",
            source_detail=data.get("source_detail", sql[:100]),
            row_count=row_count,
            dashboard_url=None,
        )
    except Exception as e:
        # Safe fallback — build minimal evidence directly from results
        return Evidence(
            claim=f"Query returned {row_count} rows for: {gap.question}",
            claim_type="proven",
            confidence="LOW",
            is_verified=True,
            source=f"sql:{gap.suggested_table}",
            source_detail=sql[:100],
            row_count=row_count,
            dashboard_url=None,
        )