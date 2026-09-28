from typing import Literal

from pydantic import BaseModel, Field


class ScheduleRequest(BaseModel):
    planning_horizon_days: int = Field(default=5, ge=1, le=5)
    objective: Literal["balanced", "due_date", "changeover"] = "balanced"
    request_text: str | None = Field(default=None, max_length=1000)


class ScheduleIntent(BaseModel):
    planning_horizon_days: int = Field(ge=1, le=5)
    objective: Literal["balanced", "due_date", "changeover"]


class ApprovalDecision(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    comment: str | None = Field(default=None, max_length=2000)


class ManifestResponse(BaseModel):
    manifest: dict


class ScheduleRunResponse(BaseModel):
    run_id: str
    status: str
    result: dict


class RunSummary(BaseModel):
    id: str
    agent_id: str
    status: str
    created_at: str
    result: dict | None
