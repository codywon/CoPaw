# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

SubagentTaskStatus = Literal[
    "queued",
    "running",
    "success",
    "error",
    "timeout",
    "cancelled",
]


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
