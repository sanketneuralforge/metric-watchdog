# tests/evals/test_reasoning.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from tests.evals.fixtures import (
    get_test_reading_with_anomalies,
    get_test_reading_normal,
    get_test_reasoning_critical,
)
from agents.reasoning_agent import run as run_reasoning


class TestReasoningStructure:

    def test_output_has_required_fields(self):
        reasoning = get_test_reasoning_critical()
        assert reasoning.overall_severity in ["CRITICAL", "WARNING", "NORMAL"]
        assert isinstance(reasoning.concerning_metrics, list)
        assert isinstance(reasoning.gaps, list)
        assert reasoning.narrative

    def test_gaps_have_required_fields(self):
        reasoning = get_test_reasoning_critical()
        for gap in reasoning.gaps:
            assert gap.question
            assert gap.metric_name
            assert gap.suggested_table
            assert gap.priority in ["HIGH", "MEDIUM", "LOW"]
            assert gap.suggested_next_step


class TestReasoningBehavioral:

    def test_critical_reading_produces_concerning_metrics(self):
        """CRITICAL reading must produce at least one concerning metric."""
        reasoning = get_test_reasoning_critical()
        assert len(reasoning.concerning_metrics) >= 1

    def test_critical_reading_produces_gaps(self):
        """CRITICAL reading must produce investigation gaps."""
        reasoning = get_test_reasoning_critical()
        assert len(reasoning.gaps) >= 1, \
            "CRITICAL severity must produce at least one gap to investigate"

    def test_gap_metric_names_in_concerning(self):
        """
        Gap metric_names should match concerning metrics.
        This is the semantic matching test.
        """
        reasoning = get_test_reasoning_critical()
        concerning_lower = {m.lower() for m in reasoning.concerning_metrics}
        for gap in reasoning.gaps:
            # Allow fuzzy match — gap metric may be substring
            matched = any(
                gap.metric_name.lower() in c or c in gap.metric_name.lower()
                for c in concerning_lower
            )
            assert matched, \
                f"Gap metric '{gap.metric_name}' not in concerning metrics"

    @pytest.mark.slow
    def test_live_reasoning_on_anomaly_dashboard(self):
        """
        Live test — runs actual LLM call.
        Marked slow to avoid burning quota on every run.
        """
        reading = get_test_reading_with_anomalies()
        reasoning = run_reasoning(reading)
        assert reasoning.overall_severity in ["CRITICAL", "WARNING"]
        assert len(reasoning.concerning_metrics) >= 1
        assert len(reasoning.gaps) >= 1

    @pytest.mark.slow
    def test_live_reasoning_on_normal_dashboard(self):
        """Normal dashboard should not produce CRITICAL severity."""
        reading = get_test_reading_normal()
        reasoning = run_reasoning(reading)
        assert reasoning.overall_severity != "CRITICAL"