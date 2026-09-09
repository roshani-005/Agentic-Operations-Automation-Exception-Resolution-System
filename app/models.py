from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    task: str = Field(min_length=5, max_length=2000)


class PlanStep(BaseModel):
    name: str
    tool: Literal["sql", "api", "python"]
    input: dict[str, Any] = Field(default_factory=dict)


class AgentPlan(BaseModel):
    objective: str
    steps: list[PlanStep]


class ToolResult(BaseModel):
    tool: str
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class VerificationResult(BaseModel):
    valid: bool
    reason: str
    needs_human_review: bool = False


class AuditEvent(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    stage: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class TaskState(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    task: str
    plan: AgentPlan | None = None
    current_step: int = 0
    tool_results: list[ToolResult] = Field(default_factory=list)
    verification: VerificationResult | None = None
    retry_count: int = 0
    final_status: Literal["running", "completed", "human_review", "failed"] = "running"
    final_answer: str | None = None
    audit_log: list[AuditEvent] = Field(default_factory=list)


class TaskResponse(BaseModel):
    task_id: str
    status: str
    answer: str | None
    retries: int
    audit_log: list[AuditEvent]
