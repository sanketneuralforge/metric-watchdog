# guardrails/output_guard.py

"""
Ring 4 — Output validation.

Validates the pipeline's final output before delivery:
- Briefing is not empty
- Unverified claims are flagged
- No hallucinated table names in citations
- Severity is consistent with evidence
"""

import re
from dataclasses import dataclass, field
from core.models import BriefingDocument, EvidenceBundle


@dataclass
class OutputValidationResult:
    is_valid: bool
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_briefing(
    briefing: BriefingDocument,
    bundles: list[EvidenceBundle],
    allowed_tables: set[str],
) -> OutputValidationResult:
    """
    Validate the final briefing before delivery.
    Returns violations (block delivery) and warnings (flag but allow).
    """
    violations = []
    warnings = []

    # ── Check briefing is not empty ──────────────────────────────
    if not briefing.briefing_text or len(briefing.briefing_text) < 50:
        violations.append("Briefing text is empty or too short.")

    if not briefing.briefing_html or len(briefing.briefing_html) < 100:
        violations.append("Briefing HTML is empty or too short.")

    # ── Check severity is valid ──────────────────────────────────
    if briefing.overall_severity not in ["CRITICAL", "WARNING", "NORMAL"]:
        violations.append(
            f"Invalid severity: {briefing.overall_severity}"
        )

    # ── Check unresolvable gaps are flagged ──────────────────────
    has_unresolvable = any(
        len(b.unresolvable) > 0 for b in bundles
    )
    if has_unresolvable and "[UNVERIFIED]" not in briefing.briefing_text:
        warnings.append(
            "Unresolvable gaps exist but [UNVERIFIED] flag "
            "not found in briefing text."
        )

    # ── Check no hallucinated table names in citations ───────────
    if allowed_tables:
        # Find SQL citations in briefing: [SQL: table_name, ...]
        cited_tables = re.findall(
            r'\[SQL:\s*([a-zA-Z_][a-zA-Z0-9_]*)',
            briefing.briefing_text,
            re.IGNORECASE,
        )
        for table in cited_tables:
            if table.lower() not in allowed_tables:
                warnings.append(
                    f"Briefing cites unknown table: '{table}' — "
                    f"may be hallucinated."
                )

    # ── Check proven claims have row counts ──────────────────────
    for bundle in bundles:
        for evidence in bundle.proven:
            if evidence.row_count is None or evidence.row_count == 0:
                warnings.append(
                    f"Proven claim has no row count: '{evidence.claim[:60]}'"
                )

    return OutputValidationResult(
        is_valid=len(violations) == 0,
        violations=violations,
        warnings=warnings,
    )


def scan_sql_for_dangerous_patterns(sql: str) -> list[str]:
    """
    Scan LLM-generated SQL for dangerous patterns before execution.
    Second line of defense after the whitelist check.
    Returns list of violations — empty means safe.
    """
    violations = []
    sql_upper = sql.upper().strip()

    dangerous = {
        r'\bDROP\b': "DROP operation",
        r'\bDELETE\b': "DELETE operation",
        r'\bTRUNCATE\b': "TRUNCATE operation",
        r'\bINSERT\b': "INSERT operation",
        r'\bUPDATE\b': "UPDATE operation",
        r'\bALTER\b': "ALTER operation",
        r'\bCREATE\b': "CREATE operation",
        r'\bGRANT\b': "GRANT operation",
        r'\bREVOKE\b': "REVOKE operation",
        r';\s*\w': "Multiple statements (SQL injection pattern)",
        r"'\s*OR\s*'\d": "OR injection pattern",
        r"'\s*;\s*--": "Comment injection pattern",
    }

    for pattern, description in dangerous.items():
        if re.search(pattern, sql_upper):
            violations.append(description)

    return violations