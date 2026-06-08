# core/scheduler.py

"""
APScheduler — runs the pipeline automatically at a configured time.
Manual trigger available via CLI and Streamlit UI.

Schedule is configured via config/schedule.yaml:
  hour: 8
  minute: 0
  timezone: Europe/London
"""

import yaml
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


def load_schedule() -> dict:
    schedule_file = Path("config/schedule.yaml")
    if not schedule_file.exists():
        return {
            "hour": 8,
            "minute": 0,
            "timezone": "UTC",
            "dashboard_path": "dashboard.png",
            "enabled": True,
        }
    with open(schedule_file) as f:
        return yaml.safe_load(f)


def create_scheduler(pipeline_fn) -> BackgroundScheduler:
    """
    Create and configure the background scheduler.
    pipeline_fn: callable that takes image_path and runs the pipeline.
    """
    schedule = load_schedule()
    scheduler = BackgroundScheduler()

    if schedule.get("enabled", True):
        scheduler.add_job(
            func=pipeline_fn,
            trigger=CronTrigger(
                hour=schedule["hour"],
                minute=schedule["minute"],
                timezone=schedule.get("timezone", "UTC"),
            ),
            kwargs={"image_path": schedule.get("dashboard_path", "dashboard.png")},
            id="morning_briefing",
            name="Morning Intelligence Briefing",
            replace_existing=True,
        )

    return scheduler