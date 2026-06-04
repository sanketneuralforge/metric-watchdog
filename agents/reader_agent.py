# agents/reader_agent.py

"""
Step 1 — Reads the dashboard image using Gemini vision.
Converts raw vision output into typed DashboardReading.
"""

from core.vision import read_dashboard_image
from core.models import DashboardReading, MetricObservation


def run(image_path: str) -> DashboardReading:
    """
    Read a dashboard screenshot and return structured observations.
    This is the only agent that uses Gemini — all others use Groq.
    """
    print(f"  [reader] Reading dashboard: {image_path}")

    raw = read_dashboard_image(image_path)

    metrics = []
    for m in raw.get("metrics", []):
        metrics.append(MetricObservation(
            name=m.get("name", "unknown"),
            value=m.get("value", "unknown"),
            unit=m.get("unit", ""),
            direction=m.get("direction", "unknown"),
            comparison=m.get("comparison", ""),
            change_value=m.get("change_value"),
            change_pct=m.get("change_pct"),
            confidence=m.get("confidence", "MEDIUM"),
            source="dashboard",
        ))

    reading = DashboardReading(
    metrics=metrics,
    time_period=raw.get("time_period", "unknown"),
    dashboard_title=raw.get("dashboard_title", ""),
    charts_described=[
        str(c) if not isinstance(c, str) else c
        for c in raw.get("charts_described", [])
    ],
    reading_notes=raw.get("reading_notes", ""),
    image_path=image_path,
)
    print(f"  [reader] Extracted {len(metrics)} metrics")
    return reading