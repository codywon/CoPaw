# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

from ...config import SubagentRoleConfig
from .models import (
    SubagentTask,
    SubagentTaskEvent,
    SubagentTaskEventType,
    SubagentTaskStatus,
)


class TaskStore(Protocol):
    def create_task(
        self,
        *,
        parent_session_id: str,
        task_prompt: str,
        origin_user_id: str = "",
        origin_channel: str = "",
        label: str = "",
        role_key: str = "",
        dispatch_reason: str = "",
        parent_task_id: str = "",
        max_attempts: int = 1,
        write_mode: str = "worktree",
        allowed_paths: Optional[list[str]] = None,
        selected_model_provider: str = "",
        selected_model_name: str = "",
        reasoning_effort: str = "",
        model_fallback_used: bool = False,
        cost_estimate_usd: Optional[float] = None,
    ) -> str:
        ...

    def list_tasks(self) -> list[SubagentTask]:
        ...

    def get_task(self, task_id: str) -> Optional[SubagentTask]:
        ...

    def set_status(
        self,
        task_id: str,
        status: SubagentTaskStatus,
        *,
        result_summary: str = "",
        error_message: str = "",
    ) -> Optional[SubagentTask]:
        ...

    def set_attempt(
        self,
        task_id: str,
        attempt: int,
    ) -> Optional[SubagentTask]:
        ...

    def append_event(
        self,
        task_id: str,
        *,
        event_type: SubagentTaskEventType,
        summary: str = "",
        status: Optional[SubagentTaskStatus] = None,
        payload: Optional[dict] = None,
    ) -> Optional[SubagentTaskEvent]:
        ...

    def list_task_events(self, task_id: str) -> list[SubagentTaskEvent]:
        ...

    def get_descendant_task_ids(self, task_id: str) -> list[str]:
        ...

    def cancel_task(self, task_id: str) -> Optional[SubagentTask]:
        ...


class QueueBackend(Protocol):
    async def enqueue(self, task_id: str) -> None:
        ...

    async def dequeue(self) -> Optional[str]:
        ...

    def qsize(self) -> int:
        ...

    def close(self) -> None:
        ...


@dataclass(frozen=True)
class ModelTarget:
    provider: str
    model: str


@dataclass(frozen=True)
class ModelPlan:
    primary: ModelTarget
    fallbacks: list[ModelTarget] = field(default_factory=list)
    max_tokens: Optional[int] = None
    reasoning_effort: str = ""


class ModelRouter(Protocol):
    def select(
        self,
        role: Optional[SubagentRoleConfig],
        task_ctx: dict,
    ) -> ModelPlan:
        ...
