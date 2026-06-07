# agents/narrator_agent.py

"""
Step 4 — Writes the sourced briefing from evidence bundles.

The narrator receives pre-computed evidence and writes a structured
briefing. It cannot originate facts — every claim must trace back
to a proven, inferred, or hypothesised evidence item.

Unsourced claims are flagged [UNVERIFIED] — never silently included.
"""

import json
from core.models import (
    EvidenceBundle, ReasoningOutput,
    DashboardReading, BriefingSection, BriefingDocument
)
from core.llm import call_llm, parse_json_response
from datetime import datetime

NARRATOR_PROMPT = """
You are a senior data analyst writing a morning intelligence briefing.

You will be given:
1. Dashboard reading — what was observed in the image
2. Reasoning output — what looked concerning and why
3. Evidence bundles — proven SQL results, inferred patterns, unresolvable gaps

Your job: write a structured briefing with THREE sections per metric:

SECTION 1 — WHAT WE KNOW
Only include claims backed by proven evidence (SQL results).
Cite the source for every claim: [dashboard] or [SQL: table_name, N rows]
Include actual numbers. Be specific.

SECTION 2 — WHAT WE INFERRED
Co-moving metrics, patterns visible in the dashboard.
Cite which metrics moved together and in what window.
Never present inference as fact.

SECTION 3 — WHAT WE COULDN'T CHECK
List every unresolvable gap explicitly.
For each: state what couldn't be verified and suggest where to look.
This section is as important as the others — do not skip it.

FLAGGING RULES:
- Any claim not backed by evidence → add [UNVERIFIED] inline
- Any claim stress-tested and found weak → add [CONTESTED] inline
- Any recommendation for immediate irreversible action → add [HIGH STAKES] inline

TONE: Direct. Data-first. No filler phrases.
Write for a data team audience unless specified otherwise.

Return ONLY valid JSON — no markdown, no preamble:
{
  "sections": [
    {
      "metric_name": "metric name",
      "severity": "CRITICAL | WARNING | NORMAL",
      "what_we_know": [
        {
          "claim": "specific claim with number",
          "citation": "[dashboard] or [SQL: table, N rows]",
          "is_verified": true
        }
      ],
      "what_we_inferred": [
        {
          "claim": "inference statement",
          "basis": "which metrics moved together",
          "confidence": "HIGH | MEDIUM | LOW"
        }
      ],
      "what_we_couldnt_check": [
        {
          "gap": "what could not be verified",
          "suggested_action": "where analyst should look"
        }
      ],
      "headline": "one sentence summary of the most important finding"
    }
  ],
  "overall_severity": "CRITICAL | WARNING | NORMAL",
  "executive_summary": "2-3 sentences covering the most critical finding only",
  "recommended_actions": [
    {
      "action": "specific next step",
      "priority": "immediate | today | this_week",
      "effort": "15min | 1hr | half_day"
    }
  ]
}
"""


def run(
    reading: DashboardReading,
    reasoning: ReasoningOutput,
    bundles: list[EvidenceBundle],
    log: RunLog | None = None,
) -> BriefingDocument:
    import time
    start = time.time()

    if log:
        log.stage_start("narrator")
        log.info("narrator", f"Writing briefing for {len(bundles)} metrics")

    print(f"  [narrator] Writing briefing for {len(bundles)} metrics...")

    evidence_text = _format_evidence_for_prompt(bundles)
    reasoning_text = _format_reasoning_for_prompt(reasoning)
    reading_text = _format_reading_for_prompt(reading)

    user_message = f"""
DASHBOARD READING:
{reading_text}

REASONING OUTPUT:
{reasoning_text}

EVIDENCE BUNDLES:
{evidence_text}

Write the sourced briefing now.
"""

    try:
        raw = call_llm(
            system_prompt=NARRATOR_PROMPT,
            user_message=user_message,
        )
        data = parse_json_response(raw)
    except Exception as e:
        if log:
            log.error("narrator", f"LLM failed: {e}")
        data = _fallback_briefing(reasoning, bundles)

    briefing = _build_briefing_document(data, reading, reasoning, bundles)

    duration_ms = int((time.time() - start) * 1000)

    if log:
        log.info("narrator", f"Severity: {briefing.overall_severity}")
        log.info("narrator", f"Sections: {len(briefing.sections)}")
        log.stage_end("narrator", duration_ms)

    print(f"  [narrator] Briefing complete — "
          f"{len(briefing.sections)} sections, "
          f"severity: {briefing.overall_severity}")

    return briefing


def _format_evidence_for_prompt(bundles: list[EvidenceBundle]) -> str:
    lines = []
    for bundle in bundles:
        lines.append(f"\nMetric: {bundle.metric_name} [{bundle.severity}]")

        if bundle.proven:
            lines.append("  Proven (from SQL):")
            for e in bundle.proven:
                lines.append(f"    - {e.claim} "
                             f"[{e.source}, n={e.row_count}, "
                             f"confidence={e.confidence}]")

        if bundle.inferred:
            lines.append("  Inferred (co-movement):")
            for e in bundle.inferred:
                lines.append(f"    - {e.claim} [confidence={e.confidence}]")

        if bundle.unresolvable:
            lines.append("  Could not check:")
            for u in bundle.unresolvable:
                lines.append(f"    - {u.gap.question}")
                lines.append(f"      Reason: {u.failure_reason}")
                lines.append(f"      Suggest: {u.suggested_next_step}")

    return "\n".join(lines)


def _format_reasoning_for_prompt(reasoning: ReasoningOutput) -> str:
    return f"""
Severity: {reasoning.overall_severity}
Concerning metrics: {reasoning.concerning_metrics}
Narrative: {reasoning.narrative}
Co-moving pairs: {reasoning.co_moving_pairs}
"""


def _format_reading_for_prompt(reading: DashboardReading) -> str:
    metrics_text = "\n".join([
        f"  - {m.name}: {m.value} {m.unit} ({m.direction})"
        for m in reading.metrics
    ])
    return f"""
Dashboard: {reading.dashboard_title}
Period: {reading.time_period}
Metrics seen:
{metrics_text}
"""


def _fallback_briefing(
    reasoning: ReasoningOutput,
    bundles: list[EvidenceBundle],
) -> dict:
    """Safe fallback if narrator LLM call fails."""
    sections = []
    for bundle in bundles:
        proven_claims = [
            {
                "claim": e.claim,
                "citation": f"[{e.source}, {e.row_count} rows]",
                "is_verified": True,
            }
            for e in bundle.proven
        ]
        gaps = [
            {
                "gap": u.gap.question,
                "suggested_action": u.suggested_next_step or "Manual investigation required",
            }
            for u in bundle.unresolvable
        ]
        sections.append({
            "metric_name": bundle.metric_name,
            "severity": bundle.severity,
            "what_we_know": proven_claims,
            "what_we_inferred": [],
            "what_we_couldnt_check": gaps,
            "headline": f"{bundle.metric_name} requires investigation",
        })

    return {
        "sections": sections,
        "overall_severity": reasoning.overall_severity,
        "executive_summary": reasoning.narrative,
        "recommended_actions": [],
    }


def _build_briefing_document(
    data: dict,
    reading: DashboardReading,
    reasoning: ReasoningOutput,
    bundles: list[EvidenceBundle],
) -> "BriefingDocument":
    from core.models import BriefingDocument, BriefingSection

    sections = []
    for s in data.get("sections", []):
        sections.append(BriefingSection(
            metric_name=s.get("metric_name", ""),
            severity=s.get("severity", "WARNING"),
            what_we_know=s.get("what_we_know", []),
            what_we_inferred=s.get("what_we_inferred", []),
            what_we_couldnt_check=s.get("what_we_couldnt_check", []),
            headline=s.get("headline", ""),
        ))

    briefing_text = _render_text(data, reading)
    briefing_html = _render_html(data, reading)

    return BriefingDocument(
        run_id=f"watchdog_{datetime.now().strftime('%Y%m%d_%H%M')}",
        date=datetime.now().strftime("%A %d %B %Y"),
        sections=sections,
        overall_severity=data.get("overall_severity", reasoning.overall_severity),
        executive_summary=data.get("executive_summary", reasoning.narrative),
        recommended_actions=data.get("recommended_actions", []),
        briefing_text=briefing_text,
        briefing_html=briefing_html,
    )


def _render_text(data: dict, reading: DashboardReading) -> str:
    """Render briefing as plain text for email/Slack."""
    lines = []
    severity = data.get("overall_severity", "WARNING")
    severity_icon = "🔴" if severity == "CRITICAL" else "🟡" if severity == "WARNING" else "🟢"

    lines.append(f"{severity_icon} METRIC WATCHDOG — {datetime.now().strftime('%A %d %B %Y, %H:%M')}")
    lines.append("━" * 50)
    lines.append("")

    # Executive summary
    if summary := data.get("executive_summary"):
        lines.append(f"SUMMARY: {summary}")
        lines.append("")

    # Per-metric sections
    for section in data.get("sections", []):
        sev = section.get("severity", "WARNING")
        sev_icon = "🔴" if sev == "CRITICAL" else "🟡" if sev == "WARNING" else "🟢"
        lines.append(f"{sev_icon} {section.get('metric_name', '').upper()}")

        if headline := section.get("headline"):
            lines.append(f"   {headline}")

        # What we know
        known = section.get("what_we_know", [])
        if known:
            lines.append("")
            lines.append("   ✅ WHAT WE KNOW")
            for item in known:
                citation = item.get("citation", "")
                lines.append(f"   • {item.get('claim', '')} {citation}")

        # What we inferred
        inferred = section.get("what_we_inferred", [])
        if inferred:
            lines.append("")
            lines.append("   📐 WHAT WE INFERRED")
            for item in inferred:
                conf = item.get("confidence", "")
                lines.append(f"   • {item.get('claim', '')} [confidence: {conf}]")

        # What we couldn't check
        gaps = section.get("what_we_couldnt_check", [])
        if gaps:
            lines.append("")
            lines.append("   ⚠️  WHAT WE COULDN'T CHECK")
            for item in gaps:
                lines.append(f"   • {item.get('gap', '')} [UNVERIFIED]")
                if action := item.get("suggested_action"):
                    lines.append(f"     → {action}")

        lines.append("")
        lines.append("━" * 50)
        lines.append("")

    # Recommended actions
    actions = data.get("recommended_actions", [])
    if actions:
        lines.append("📋 RECOMMENDED ACTIONS")
        for a in actions:
            priority = a.get("priority", "")
            effort = a.get("effort", "")
            lines.append(f"   [{priority.upper()} — {effort}] {a.get('action', '')}")
        lines.append("")

    lines.append(f"Run ID: watchdog_{datetime.now().strftime('%Y%m%d_%H%M')}")
    lines.append(f"Dashboard: {reading.dashboard_title or 'uploaded snapshot'}")

    return "\n".join(lines)


def _render_html(data: dict, reading: DashboardReading) -> str:
    """Render briefing as HTML for email."""
    severity = data.get("overall_severity", "WARNING")
    severity_color = (
        "#dc2626" if severity == "CRITICAL"
        else "#d97706" if severity == "WARNING"
        else "#16a34a"
    )

    sections_html = ""
    for section in data.get("sections", []):
        sev = section.get("severity", "WARNING")
        sev_color = (
            "#dc2626" if sev == "CRITICAL"
            else "#d97706" if sev == "WARNING"
            else "#16a34a"
        )

        known_html = ""
        for item in section.get("what_we_know", []):
            known_html += f"""
            <li>
                {item.get('claim', '')}
                <span style="color:#6b7280;font-size:12px;">
                    {item.get('citation', '')}
                </span>
            </li>"""

        inferred_html = ""
        for item in section.get("what_we_inferred", []):
            inferred_html += f"""
            <li>
                {item.get('claim', '')}
                <span style="color:#6b7280;font-size:12px;">
                    [confidence: {item.get('confidence', '')}]
                </span>
            </li>"""

        gaps_html = ""
        for item in section.get("what_we_couldnt_check", []):
            gaps_html += f"""
            <li>
                <span style="color:#d97706;">
                    {item.get('gap', '')} [UNVERIFIED]
                </span>
                <br>
                <span style="color:#6b7280;font-size:12px;">
                    → {item.get('suggested_action', '')}
                </span>
            </li>"""

        sections_html += f"""
        <div style="margin-bottom:24px;padding:16px;border-left:4px solid {sev_color};
                    background:#f9fafb;border-radius:4px;">
            <div style="font-weight:700;font-size:16px;color:{sev_color};
                        margin-bottom:8px;">
                {section.get('metric_name', '').upper()}
            </div>
            <div style="color:#374151;margin-bottom:12px;font-style:italic;">
                {section.get('headline', '')}
            </div>
            {'<div style="margin-bottom:10px;"><strong style="color:#16a34a;">✅ What We Know</strong><ul>' + known_html + '</ul></div>' if known_html else ''}
            {'<div style="margin-bottom:10px;"><strong style="color:#2563eb;">📐 What We Inferred</strong><ul>' + inferred_html + '</ul></div>' if inferred_html else ''}
            {'<div style="margin-bottom:10px;"><strong style="color:#d97706;">⚠️ What We Couldn\'t Check</strong><ul>' + gaps_html + '</ul></div>' if gaps_html else ''}
        </div>"""

    actions_html = ""
    for a in data.get("recommended_actions", []):
        actions_html += f"""
        <li>
            <strong>[{a.get('priority', '').upper()} — {a.get('effort', '')}]</strong>
            {a.get('action', '')}
        </li>"""

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;
             padding:20px;color:#111827;">

    <div style="background:{severity_color};color:white;padding:16px 20px;
                border-radius:8px;margin-bottom:24px;">
        <div style="font-size:20px;font-weight:700;">
            📊 Metric Watchdog
        </div>
        <div style="font-size:14px;opacity:0.9;">
            {datetime.now().strftime('%A %d %B %Y, %H:%M')} ·
            {severity}
        </div>
    </div>

    <div style="background:#f3f4f6;padding:16px;border-radius:8px;
                margin-bottom:24px;font-size:15px;color:#374151;">
        {data.get('executive_summary', '')}
    </div>

    {sections_html}

    {'<div style="margin-top:24px;padding:16px;background:#eff6ff;border-radius:8px;"><strong>📋 Recommended Actions</strong><ul>' + actions_html + '</ul></div>' if actions_html else ''}

    <div style="margin-top:24px;font-size:12px;color:#9ca3af;
                border-top:1px solid #e5e7eb;padding-top:12px;">
        Run ID: watchdog_{datetime.now().strftime('%Y%m%d_%H%M')} ·
        Dashboard: {reading.dashboard_title or 'uploaded snapshot'}
    </div>

</body>
</html>"""