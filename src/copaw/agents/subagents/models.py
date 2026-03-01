# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

SubagentTaskStatus = Literal[
    "queued",
    "running",
    "success",
    "error",
    "timeout",
    "cancelled",
]
SubagentTaskEventType = Literal[
    "dispatch",
    "model_selected",
    "tool_call",
    "tool_result",
    "status_change",
    "error",
]


class SubagentTaskEvent(BaseModel):
    """Subagent task event for timeline and audit."""

    event_id: str
    task_id: str
    ts: datetime
    type: SubagentTaskEventType
    summary: str = ""
    status: Optional[SubagentTaskStatus] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class SubagentTask(BaseModel):
    """Subagent task lifecycle snapshot."""

    task_id: str
    status: SubagentTaskStatus = "queued"
    parent_session_id: str = ""
    origin_user_id: str = ""
    origin_channel: str = ""
    label: str = ""
    role_key: str = ""
    dispatch_reason: str = ""
    parent_task_id: str = ""
    task_prompt: str = ""
    write_mode: str = "worktree"
    allowed_paths: List[str] = Field(default_factory=list)
    selected_model_provider: str = ""
    selected_model_name: str = ""
    reasoning_effort: str = ""
    model_fallback_used: bool = False
    cost_estimate_usd: Optional[float] = None
    attempts: int = 0
    max_attempts: int = 1
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    result_summary: str = ""
    artifacts: Dict[str, str] = Field(default_factory=dict)
    error_message: str = ""


class SubagentTaskListResponse(BaseModel):
    """Paginated task list response."""

    items: List[SubagentTask] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


class SubagentTaskEventListResponse(BaseModel):
    """Task event timeline response."""

    task_id: str
    items: List[SubagentTaskEvent] = Field(default_factory=list)


class SubagentModelOption(BaseModel):
    id: str
    name: str


class SubagentModelProviderOption(BaseModel):
    id: str
    name: str
    is_local: bool = False
    has_api_key: bool = False
    models: List[SubagentModelOption] = Field(default_factory=list)


class SubagentRoleModelOptionsResponse(BaseModel):
    active_provider_id: str = ""
    active_model: str = ""
    providers: List[SubagentModelProviderOption] = Field(default_factory=list)
