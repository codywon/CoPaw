# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .models import SubagentTask, SubagentTaskStatus

_TERMINAL_STATUSES: set[SubagentTaskStatus] = {
    "success",
    "error",
    "timeout",
    "cancelled",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class InMemorySubagentTaskStore:
    """Thread-safe in-memory subagent task store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: Dict[str, SubagentTask] = {}
        self._children: Dict[str, set[str]] = {}

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
        allowed_paths: Optional[List[str]] = None,
    ) -> str:
        task_id = str(uuid.uuid4())
        task = SubagentTask(
            task_id=task_id,
            status="queued",
            parent_session_id=parent_session_id,
            task_prompt=task_prompt,
            origin_user_id=origin_user_id,
            origin_channel=origin_channel,
            label=label,
            role_key=role_key,
            dispatch_reason=dispatch_reason,
            parent_task_id=parent_task_id,
            write_mode=write_mode,
            allowed_paths=list(allowed_paths or []),
            max_attempts=max(1, int(max_attempts)),
        )
        with self._lock:
            self._tasks[task_id] = task
            if parent_task_id:
                bucket = self._children.get(parent_task_id)
                if bucket is None:
                    bucket = set()
                    self._children[parent_task_id] = bucket
                bucket.add(task_id)
        return task_id

    def list_tasks(self) -> List[SubagentTask]:
        with self._lock:
            return [task.model_copy(deep=True) for task in self._tasks.values()]

    def get_task(self, task_id: str) -> Optional[SubagentTask]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            return task.model_copy(deep=True)

    def set_status(
        self,
        task_id: str,
        status: SubagentTaskStatus,
        *,
        result_summary: str = "",
        error_message: str = "",
    ) -> Optional[SubagentTask]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None

            now = _utcnow()
            if status == "running":
                if task.started_at is None:
                    task.started_at = now
                task.status = status
            else:
                if task.started_at is None:
                    task.started_at = now
                task.ended_at = now
                delta = task.ended_at - task.started_at
                task.duration_ms = int(delta.total_seconds() * 1000)
                task.status = status

            if result_summary:
                task.result_summary = result_summary
            if error_message:
                task.error_message = error_message
            return task.model_copy(deep=True)

    def set_attempt(self, task_id: str, attempt: int) -> Optional[SubagentTask]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            task.attempts = max(0, int(attempt))
            return task.model_copy(deep=True)

    def get_descendant_task_ids(self, task_id: str) -> List[str]:
        with self._lock:
            descendants: list[str] = []
            queue = list(self._children.get(task_id, set()))
            visited: set[str] = set()
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                descendants.append(current)
                queue.extend(list(self._children.get(current, set())))
            return descendants

    def cancel_task(self, task_id: str) -> Optional[SubagentTask]:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return None
            if task.status in _TERMINAL_STATUSES:
                return task.model_copy(deep=True)

            now = _utcnow()
            if task.started_at is None:
                task.started_at = now
            task.ended_at = now
            delta = task.ended_at - task.started_at
            task.duration_ms = int(delta.total_seconds() * 1000)
            task.status = "cancelled"
            return task.model_copy(deep=True)


_GLOBAL_SUBAGENT_TASK_STORE = InMemorySubagentTaskStore()


def get_subagent_task_store() -> InMemorySubagentTaskStore:
    return _GLOBAL_SUBAGENT_TASK_STORE
