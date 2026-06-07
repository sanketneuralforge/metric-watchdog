# core/run_logger.py

"""
Plain text run logger — one file per day, structured format.
Watch live: tail -f logs/watchdog.log

Every pipeline stage logs to the same file with a consistent format:
[timestamp] [run_id] [stage] [status] message
"""

import os
import logging
from pathlib import Path
from datetime import datetime

LOG_DIR = Path("logs")


def get_logger(run_id: str) -> logging.Logger:
    """
    Get a logger for a specific run.
    All runs log to the same daily file — distinguished by run_id.
    """
    LOG_DIR.mkdir(exist_ok=True)

    log_file = LOG_DIR / f"watchdog_{datetime.now().strftime('%Y%m%d')}.log"
    logger_name = f"watchdog.{run_id}"

    logger = logging.getLogger(logger_name)

    # Don't add handlers if already configured
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # File handler — plain text, always appended
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    # Console handler — same output to stdout
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Format: timestamp | run_id | stage | message
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


class RunLog:
    """
    Structured logger for a single pipeline run.
    Wraps Python logger with stage-aware methods.
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.logger = get_logger(run_id)
        self.start_time = datetime.now()

    def info(self, stage: str, message: str):
        self.logger.info(f"[{stage}] {message}")

    def success(self, stage: str, message: str):
        self.logger.info(f"[{stage}] ✓ {message}")

    def warning(self, stage: str, message: str):
        self.logger.warning(f"[{stage}] ⚠ {message}")

    def error(self, stage: str, message: str):
        self.logger.error(f"[{stage}] ✗ {message}")

    def sql(self, gap_question: str, sql: str, rows: int | None = None, error: str | None = None):
        """Log a SQL generation and execution attempt."""
        self.logger.info(f"[diagnosis:sql] Gap: {gap_question[:80]}")
        self.logger.debug(f"[diagnosis:sql] Query:\n{sql}")
        if error:
            self.logger.error(f"[diagnosis:sql] FAILED: {error}")
        else:
            self.logger.info(f"[diagnosis:sql] OK — {rows} rows returned")

    def stage_start(self, stage: str):
        self.logger.info(f"[{stage}] ── START ──────────────────────")

    def stage_end(self, stage: str, duration_ms: int, status: str = "success"):
        self.logger.info(
            f"[{stage}] ── END [{status.upper()}] {duration_ms}ms ──"
        )

    def pipeline_start(self, image_path: str):
        self.logger.info("=" * 60)
        self.logger.info(f"PIPELINE START — {self.run_id}")
        self.logger.info(f"Dashboard: {image_path}")
        self.logger.info("=" * 60)

    def pipeline_end(self, severity: str, duration_s: float):
        self.logger.info("=" * 60)
        self.logger.info(
            f"PIPELINE END — {severity} — {duration_s:.1f}s"
        )
        self.logger.info("=" * 60)