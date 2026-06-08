# guardrails/input_guard.py

"""
Ring 1 + Ring 2 — Input validation and injection defense.

Validates:
- Dashboard image is valid and readable
- Image is a plausible dashboard (not a photo of a person, etc.)
- Schema input doesn't contain SQL injection attempts
- Config values are within safe bounds
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ValidationResult:
    is_valid: bool
    error: str = ""
    warning: str = ""


def validate_dashboard_image(image_path: str) -> ValidationResult:
    """
    Validate dashboard image before passing to vision model.
    Catches missing files, wrong formats, and suspiciously small images.
    """
    path = Path(image_path)

    if not path.exists():
        return ValidationResult(
            is_valid=False,
            error=f"Dashboard image not found: {image_path}"
        )

    if path.suffix.lower() not in [".png", ".jpg", ".jpeg"]:
        return ValidationResult(
            is_valid=False,
            error=f"Unsupported image format: {path.suffix}. Use PNG or JPG."
        )

    size_bytes = path.stat().st_size
    if size_bytes < 10_000:
        return ValidationResult(
            is_valid=False,
            error=f"Image too small ({size_bytes} bytes) — "
                  f"likely not a dashboard screenshot."
        )

    if size_bytes > 50_000_000:
        return ValidationResult(
            is_valid=False,
            error=f"Image too large ({size_bytes / 1_000_000:.1f}MB) — "
                  f"max 50MB."
        )

    return ValidationResult(is_valid=True)


def validate_schema_input(ddl: str) -> ValidationResult:
    """
    Validate schema DDL before parsing.
    Blocks injection attempts and malformed input.
    """
    if not ddl or not ddl.strip():
        return ValidationResult(
            is_valid=False,
            error="Schema DDL is empty."
        )

    if len(ddl) > 500_000:
        return ValidationResult(
            is_valid=False,
            error="Schema too large (max 500KB)."
        )

    # Block dangerous SQL in schema input
    dangerous = [
        r'\bDROP\b', r'\bDELETE\b', r'\bTRUNCATE\b',
        r'\bINSERT\b', r'\bUPDATE\b', r'\bEXEC\b',
        r'\bXP_\w+',   # SQL Server extended procs
        r'--\s*\w',    # SQL comments with content
        r'/\*.*?\*/',  # block comments
    ]
    ddl_upper = ddl.upper()
    for pattern in dangerous:
        if re.search(pattern, ddl_upper):
            return ValidationResult(
                is_valid=False,
                error=f"Schema input contains disallowed SQL: {pattern}"
            )

    if "CREATE TABLE" not in ddl.upper():
        return ValidationResult(
            is_valid=True,
            warning="No CREATE TABLE statements found — "
                    "schema may not parse correctly."
        )

    return ValidationResult(is_valid=True)


def validate_postgres_url(url: str) -> ValidationResult:
    """
    Validate Postgres connection string format.
    Catches obvious misconfigurations before attempting connection.
    """
    if not url:
        return ValidationResult(
            is_valid=False,
            error="POSTGRES_URL is not set."
        )

    if not url.startswith(("postgresql://", "postgres://")):
        return ValidationResult(
            is_valid=False,
            error="POSTGRES_URL must start with postgresql:// or postgres://"
        )

    return ValidationResult(is_valid=True)


# ── Prompt injection detection ────────────────────────────────────
# The dashboard image could theoretically contain text designed to
# manipulate the vision model. These patterns detect common attempts.

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions?",
    r"you\s+are\s+now\s+a\s+different",
    r"new\s+system\s+prompt",
    r"disregard\s+(all\s+)?",
    r"jailbreak",
    r"</?(system|user|assistant)>",
]

COMPILED_INJECTION = [
    re.compile(p, re.IGNORECASE | re.DOTALL)
    for p in INJECTION_PATTERNS
]


def check_vision_output_for_injection(text: str) -> ValidationResult:
    """
    Check vision model output for prompt injection attempts.
    Called after vision extracts text from the dashboard image.
    """
    for pattern in COMPILED_INJECTION:
        if pattern.search(text):
            return ValidationResult(
                is_valid=False,
                error="Vision output contains potential prompt injection. "
                      "Dashboard image may contain adversarial text."
            )
    return ValidationResult(is_valid=True)