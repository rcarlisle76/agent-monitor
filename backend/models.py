from typing import Literal
from pydantic import BaseModel


class ReportRequest(BaseModel):
    agent_id: str
    parent_id: str | None = None
    replaces: str | None = None   # agent_id this agent was spawned to replace
    status: Literal["running", "idle", "completed", "error", "terminated"]
    task: str | None = None
    accuracy: float | None = None  # 0–100; below 70 triggers a termination flag
    metadata: dict = {}


class AgentResponse(BaseModel):
    agent_id: str
    parent_id: str | None
    replaces: str | None
    status: str
    current_task: str | None
    current_accuracy: float | None
    flagged: bool
    metadata: dict
    first_seen: str
    last_updated: str


class TaskRecord(BaseModel):
    id: int
    agent_id: str
    status: str
    task: str | None
    accuracy: float | None
    metadata: dict
    recorded_at: str


class MetricsResponse(BaseModel):
    active_agents: int
    total_agents: int
    total_tasks: int
    flagged_agents: int
    error_count: int
    error_rate: float
    avg_accuracy: float | None
    avg_duration_seconds: float | None
