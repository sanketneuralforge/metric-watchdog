# core/token_budget.py

"""
Token budget management for Metric Watchdog.
Tracks tokens per run and truncates inputs intelligently
to stay within model context limits.
"""

from dataclasses import dataclass, field
from core.schema import SchemaContext, TableSchema


@dataclass
class TokenUsage:
    """Tracks token usage across a pipeline run."""
    run_id: str
    vision_input: int = 0
    vision_output: int = 0
    reasoning_input: int = 0
    reasoning_output: int = 0
    diagnosis_input: int = 0
    diagnosis_output: int = 0
    narrator_input: int = 0
    narrator_output: int = 0

    def total_input(self) -> int:
        return (self.vision_input + self.reasoning_input +
                self.diagnosis_input + self.narrator_input)

    def total_output(self) -> int:
        return (self.vision_output + self.reasoning_output +
                self.diagnosis_output + self.narrator_output)

    def total(self) -> int:
        return self.total_input() + self.total_output()

    def estimated_cost_usd(self, provider: str = "groq") -> float:
        """
        Rough cost estimate based on provider pricing.
        Groq llama-3.3-70b: ~$0.59/1M input, $0.79/1M output
        """
        if provider == "groq":
            return (
                self.total_input() * 0.59 / 1_000_000 +
                self.total_output() * 0.79 / 1_000_000
            )
        return 0.0

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "total_tokens": self.total(),
            "input_tokens": self.total_input(),
            "output_tokens": self.total_output(),
            "estimated_cost_usd": self.estimated_cost_usd(),
            "breakdown": {
                "vision": self.vision_input + self.vision_output,
                "reasoning": self.reasoning_input + self.reasoning_output,
                "diagnosis": self.diagnosis_input + self.diagnosis_output,
                "narrator": self.narrator_input + self.narrator_output,
            }
        }


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def trim_schema_for_prompt(
    schema: SchemaContext,
    max_tokens: int = 800,
) -> str:
    """
    Trim schema to fit within token budget.
    Prioritises tables most likely to be relevant.
    Truncates column lists for large tables.
    """
    priority_tables = ["orders", "sessions", "refunds", "campaign_calendar"]

    lines = ["Available tables and columns:"]
    token_count = estimate_tokens("\n".join(lines))

    # Add priority tables first
    tables_by_priority = sorted(
        schema.tables,
        key=lambda t: (
            0 if t.name.lower() in priority_tables
            else 1
        )
    )

    for table in tables_by_priority:
        table_lines = [f"\nTable: {table.name}", "  Columns:"]
        cols = table.columns

        # Truncate column list if too many
        if len(cols) > 15:
            cols = cols[:15]
            table_lines.append("  (showing first 15 columns)")

        for col in cols:
            table_lines.append(f"    - {col}")

        addition = "\n".join(table_lines)
        if token_count + estimate_tokens(addition) > max_tokens:
            lines.append(f"\n[Schema truncated at {max_tokens} token budget]")
            break

        lines.extend(table_lines)
        token_count += estimate_tokens(addition)

    return "\n".join(lines)