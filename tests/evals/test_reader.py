# tests/evals/test_reader.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from tests.evals.fixtures import get_test_reading_with_anomalies


class TestDashboardReadingStructure:
    """Level 1 — structural evals on DashboardReading."""

    def test_reading_has_metrics_list(self):
        reading = get_test_reading_with_anomalies()
        assert isinstance(reading.metrics, list)

    def test_reading_has_required_fields(self):
        reading = get_test_reading_with_anomalies()
        assert reading.dashboard_title
        assert reading.time_period
        assert reading.image_path

    def test_metrics_have_required_fields(self):
        reading = get_test_reading_with_anomalies()
        for m in reading.metrics:
            assert m.name
            assert m.value
            assert m.direction in ["up", "down", "flat", "unknown"]
            assert m.confidence in ["HIGH", "MEDIUM", "LOW"]

    def test_at_least_one_metric(self):
        reading = get_test_reading_with_anomalies()
        assert len(reading.metrics) >= 1, "Reading must have at least 1 metric"

    def test_direction_values_are_valid(self):
        reading = get_test_reading_with_anomalies()
        valid = {"up", "down", "flat", "unknown"}
        for m in reading.metrics:
            assert m.direction in valid, \
                f"Invalid direction: {m.direction}"


class TestDashboardReadingBehavioral:

    def test_anomaly_reading_has_down_metrics(self):
        """A reading with anomalies should have at least one 'down' metric."""
        reading = get_test_reading_with_anomalies()
        down_metrics = [m for m in reading.metrics if m.direction == "down"]
        assert len(down_metrics) >= 1, \
            "Anomaly reading should have at least one declining metric"

    def test_reading_notes_populated(self):
        reading = get_test_reading_with_anomalies()
        assert reading.reading_notes is not None