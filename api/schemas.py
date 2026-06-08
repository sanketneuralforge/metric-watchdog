# api/schemas.py

from pydantic import BaseModel
from typing import Optional


class RunRequest(BaseModel):
    """Request body for triggering a pipeline run via API."""
    dashboard_path: str
    schema_path: Optional[str] = None
    force: bool = False     # bypass idempotency check


class RunResponse(BaseModel):
    run_id: str
    severity: str
    metrics_read: int
    proven_claims: int
    unresolved_gaps: int
    duration_seconds: float
    status: str
    briefing_summary: str
    html_path: str


class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    vision_provider: str
    postgres_connected: bool
    last_run_id: Optional[str] = None
    last_run_severity: Optional[str] = None