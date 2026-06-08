# tests/evals/test_pipeline.py

"""
End-to-end pipeline eval.
Uses text input (no vision) to test full pipeline quality
without consuming vision model quota.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from tests.evals.fixtures import (
    get_test_reading_with_anomalies,
    get_test_reasoning_critical,
    get_test_schema,
)
from core import db


@pytest.mark.slow
class TestFullPipeline:

    def test_pipeline_produces_briefing(self):
        """Full pipeline must produce a non-empty briefing."""
        from agents.diagnosis_agent import run as run_diagnosis
        from agents.narrator_agent import run as run_narrator

        reading = get_test_reading_with_anomalies()
        reasoning = get_test_reasoning_critical()
        schema = get_test_schema()
        db.set_allowed_tables(schema.table_names())

        bundles = run_diagnosis(reasoning, schema)
        briefing = run_narrator(reading, reasoning, bundles)

        assert briefing is not None
        assert briefing.briefing_text
        assert briefing.overall_severity in ["CRITICAL", "WARNING", "NORMAL"]

    def test_critical_pipeline_produces_critical_briefing(self):
        """CRITICAL input must produce CRITICAL or WARNING briefing."""
        from agents.diagnosis_agent import run as run_diagnosis
        from agents.narrator_agent import run as run_narrator

        reading = get_test_reading_with_anomalies()
        reasoning = get_test_reasoning_critical()
        schema = get_test_schema()
        db.set_allowed_tables(schema.table_names())

        bundles = run_diagnosis(reasoning, schema)
        briefing = run_narrator(reading, reasoning, bundles)

        assert briefing.overall_severity in ["CRITICAL", "WARNING"], \
            "CRITICAL input must not produce NORMAL briefing"

    def test_pipeline_proven_claims_have_sources(self):
        """Every proven claim must have a non-empty source."""
        from agents.diagnosis_agent import run as run_diagnosis

        reasoning = get_test_reasoning_critical()
        schema = get_test_schema()
        db.set_allowed_tables(schema.table_names())

        bundles = run_diagnosis(reasoning, schema)
        for bundle in bundles:
            for evidence in bundle.proven:
                assert evidence.source, \
                    f"Proven claim missing source: {evidence.claim}"
                assert evidence.is_verified is True

    def test_unresolvable_gaps_have_next_steps(self):
        """Every unresolvable gap must have a suggested next step."""
        from agents.diagnosis_agent import run as run_diagnosis

        reasoning = get_test_reasoning_critical()
        schema = get_test_schema()
        db.set_allowed_tables(schema.table_names())

        bundles = run_diagnosis(reasoning, schema)
        for bundle in bundles:
            for u in bundle.unresolvable:
                assert u.suggested_next_step, \
                    f"Unresolvable gap missing next step: {u.gap.question}"