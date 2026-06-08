# tests/evals/test_narrator.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from tests.evals.fixtures import (
    get_test_reading_with_anomalies,
    get_test_reasoning_critical,
    get_populated_evidence_bundle,
)
from tests.evals.llm_judge import judge


class TestNarratorStructure:

    @pytest.mark.slow
    def test_briefing_has_required_fields(self):
        from agents.narrator_agent import run as run_narrator
        reading = get_test_reading_with_anomalies()
        reasoning = get_test_reasoning_critical()
        bundles = [get_populated_evidence_bundle()]
        briefing = run_narrator(reading, reasoning, bundles)

        assert briefing.overall_severity in ["CRITICAL", "WARNING", "NORMAL"]
        assert briefing.briefing_text
        assert briefing.briefing_html
        assert len(briefing.sections) >= 1

    @pytest.mark.slow
    def test_briefing_text_is_not_empty(self):
        from agents.narrator_agent import run as run_narrator
        reading = get_test_reading_with_anomalies()
        reasoning = get_test_reasoning_critical()
        bundles = [get_populated_evidence_bundle()]
        briefing = run_narrator(reading, reasoning, bundles)
        assert len(briefing.briefing_text) > 100

    @pytest.mark.slow
    def test_unverified_flag_appears_for_gaps(self):
        """
        When there are unresolvable gaps, [UNVERIFIED] must appear
        in the briefing text.
        """
        from agents.narrator_agent import run as run_narrator
        reading = get_test_reading_with_anomalies()
        reasoning = get_test_reasoning_critical()
        bundles = [get_populated_evidence_bundle()]
        briefing = run_narrator(reading, reasoning, bundles)
        assert "[UNVERIFIED]" in briefing.briefing_text, \
            "Unresolved gaps must be flagged [UNVERIFIED] in briefing"

    @pytest.mark.slow
    def test_briefing_mentions_concerning_metrics(self):
        """Briefing must reference the metrics that were concerning."""
        from agents.narrator_agent import run as run_narrator
        reading = get_test_reading_with_anomalies()
        reasoning = get_test_reasoning_critical()
        bundles = [get_populated_evidence_bundle()]
        briefing = run_narrator(reading, reasoning, bundles)
        assert "revenue" in briefing.briefing_text.lower() or \
               "Revenue" in briefing.briefing_text, \
               "Briefing must mention the concerning revenue metric"

    @pytest.mark.slow
    def test_semantic_briefing_is_sourced(self):
        """LLM judge checks that claims are sourced."""
        from agents.narrator_agent import run as run_narrator
        reading = get_test_reading_with_anomalies()
        reasoning = get_test_reasoning_critical()
        bundles = [get_populated_evidence_bundle()]
        briefing = run_narrator(reading, reasoning, bundles)

        verdict = judge(
            output=briefing.briefing_text,
            property_to_evaluate=(
                "Does this briefing cite sources for its claims? "
                "Look for [dashboard], [SQL:...], or [UNVERIFIED] tags. "
                "A good briefing attributes every claim."
            ),
        )
        assert verdict["pass"], f"Briefing not properly sourced: {verdict['reason']}"