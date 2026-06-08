# tests/evals/test_diagnosis.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from tests.evals.fixtures import (
    get_test_reasoning_critical,
    get_test_schema,
    get_populated_evidence_bundle,
)
from core import db


class TestDiagnosisStructure:

    def test_evidence_bundle_has_required_fields(self):
        bundle = get_populated_evidence_bundle()
        assert bundle.metric_name
        assert bundle.severity in ["CRITICAL", "WARNING", "NORMAL"]
        assert isinstance(bundle.proven, list)
        assert isinstance(bundle.unresolvable, list)

    def test_proven_evidence_has_source(self):
        bundle = get_populated_evidence_bundle()
        for e in bundle.proven:
            assert e.source
            assert e.claim
            assert e.claim_type == "proven"
            assert e.is_verified is True

    def test_unresolvable_has_next_step(self):
        bundle = get_populated_evidence_bundle()
        for u in bundle.unresolvable:
            assert u.failure_reason
            assert u.suggested_next_step


class TestDiagnosisBehavioral:

    def test_schema_whitelist_blocks_unknown_tables(self):
        """
        SQL guard must block queries referencing tables not in schema.
        This is the security test.
        """
        schema = get_test_schema()
        db.set_allowed_tables(schema.table_names())

        from core.db import execute_query_safe
        results, error = execute_query_safe(
            "SELECT * FROM unknown_secret_table LIMIT 1"
        )
        assert error is not None, "Should have blocked unknown table"
        assert "not in schema" in error.lower() or "whitelist" in error.lower() \
               or "schema" in error.lower()

    def test_schema_allows_known_tables(self):
        """SQL guard must allow queries on whitelisted tables."""
        schema = get_test_schema()
        db.set_allowed_tables(schema.table_names())

        from core.db import execute_query_safe
        results, error = execute_query_safe(
            "SELECT COUNT(*) as n FROM orders LIMIT 1"
        )
        assert error is None, f"Should have allowed orders table: {error}"

    def test_write_operations_blocked(self):
        """Write operations must always be blocked."""
        from core.db import execute_query_safe
        _, error = execute_query_safe("DROP TABLE orders")
        assert error is not None
        assert "not allowed" in error.lower()

    @pytest.mark.slow
    def test_live_diagnosis_produces_evidence(self):
        """Live test — runs SQL against real Postgres."""
        from agents.diagnosis_agent import run as run_diagnosis
        reasoning = get_test_reasoning_critical()
        schema = get_test_schema()
        db.set_allowed_tables(schema.table_names())
        bundles = run_diagnosis(reasoning, schema)
        assert len(bundles) >= 1
        total_proven = sum(len(b.proven) for b in bundles)
        total_unresolvable = sum(len(b.unresolvable) for b in bundles)
        assert total_proven + total_unresolvable >= 1