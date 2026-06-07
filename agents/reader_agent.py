# agents/reader_agent.py

import time
from core.vision import read_dashboard_image
from core.models import DashboardReading, MetricObservation
from core.run_logger import RunLog


def run(image_path: str, log: RunLog | None = None) -> DashboardReading:
    start = time.time()
    if log:
        log.stage_start("reader")
        log.info("reader", f"Reading: {image_path}")

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

    duration_ms = int((time.time() - start) * 1000)

    if log:
        log.info("reader", f"Extracted {len(metrics)} metrics")
        for m in metrics:
            log.info("reader", f"  → {m.name}: {m.value} {m.unit} ({m.direction}, confidence={m.confidence})")
        if raw.get("reading_notes"):
            log.warning("reader", f"Notes: {raw['reading_notes']}")
        log.stage_end("reader", duration_ms)

    print(f"  [reader] Extracted {len(metrics)} metrics")
    return reading