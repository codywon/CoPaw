# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from ...config import SubagentsConfig
from .models import SubagentTask
from .protocols import ModelRouter, QueueBackend, TaskStore
from .queue import InProcQueue
from .router import LocalModelRouter
from .store import get_subagent_task_store

SubagentRunner = Callable[[], Awaitable[str]]


@dataclass
class _QueuedExecution:
    runner: SubagentRunner
    timeout_seconds: Optional[int]
    retry_max_attempts: int
    retry_backoff_seconds: int


class SubagentManager:
    """Run subagent tasks with queue, retries, and cancellation control."""

    _semaphore_lock = threading.Lock()
    _global_semaphores: dict[int, asyncio.Semaphore] = {}

    _running_tasks_lock = threading.Lock()
    _running_tasks: dict[str, asyncio.Task] = {}

    def __init__(
        self,
        *,
        max_concurrency: int,
        default_timeout_seconds: int,
        hard_timeout_seconds: int,
        store: Optional[TaskStore] = None,
        queue_backend: Optional[QueueBackend] = None,
        model_router: Optional[ModelRouter] = None,
    ) -> None:
        self._max_concurrency = max(1, max_concurrency)
        self._semaphore = self._get_global_semaphore(self._max_concurrency)
        self._default_timeout_seconds = max(1, default_timeout_seconds)
        self._hard_timeout_seconds = max(
            self._default_timeout_seconds,
            hard_timeout_seconds,
        )
        self._store = store or get_subagent_task_store()
        self._queue_backend = queue_backend or InProcQueue()
        self._model_router = model_router or LocalModelRouter()
        self._queued_executions: dict[str, _QueuedExecution] = {}
        self._queued_executions_lock = threading.Lock()
        self._dispatch_loop_task: Optional[asyncio.Task] = None
        self._dispatch_loop_lock = threading.Lock()

    @property
    def model_router(self) -> ModelRouter:
        return self._model_router

    @classmethod
    def _get_global_semaphore(cls, max_concurrency: int) -> asyncio.Semaphore:
        with cls._semaphore_lock:
            semaphore = cls._global_semaphores.get(max_concurrency)
            if semaphore is None:
                semaphore = asyncio.Semaphore(max_concurrency)
                cls._global_semaphores[max_concurrency] = semaphore
            return semaphore

    @classmethod
    def _set_running_task(cls, task_id: str, task: asyncio.Task) -> None:
        with cls._running_tasks_lock:
            cls._running_tasks[task_id] = task

    @classmethod
    def _get_running_task(cls, task_id: str) -> Optional[asyncio.Task]:
        with cls._running_tasks_lock:
            return cls._running_tasks.get(task_id)

    @classmethod
    def _clear_running_task(cls, task_id: str) -> None:
        with cls._running_tasks_lock:
            cls._running_tasks.pop(task_id, None)

    def _create_task_record(
        self,
        *,
        task_prompt: str,
        parent_session_id: str = "",
        origin_user_id: str = "",
        origin_channel: str = "",
        label: str = "",
        role_key: str = "",
        dispatch_reason: str = "",
        parent_task_id: str = "",
        write_mode: str = "worktree",
        allowed_paths: Optional[list[str]] = None,
        retry_max_attempts: int = 1,
        selected_model_provider: str = "",
        selected_model_name: str = "",
        reasoning_effort: str = "",
        model_fallback_used: bool = False,
        cost_estimate_usd: Optional[float] = None,
    ) -> str:
        task_id = self._store.create_task(
            parent_session_id=parent_session_id,
            task_prompt=task_prompt,
            origin_user_id=origin_user_id,
            origin_channel=origin_channel,
            label=label,
            role_key=role_key,
            dispatch_reason=dispatch_reason,
            parent_task_id=parent_task_id,
            write_mode=write_mode,
            allowed_paths=allowed_paths,
            max_attempts=max(1, int(retry_max_attempts)),
            selected_model_provider=selected_model_provider,
            selected_model_name=selected_model_name,
            reasoning_effort=reasoning_effort,
            model_fallback_used=model_fallback_used,
            cost_estimate_usd=cost_estimate_usd,
        )
        if selected_model_provider or selected_model_name:
            self._store.append_event(
                task_id,
                event_type="model_selected",
                summary=(
                    "Model selected: "
                    f"{selected_model_provider or '(provider-missing)'}/"
                    f"{selected_model_name or '(model-missing)'}"
                ),
                payload={
                    "provider": selected_model_provider,
                    "model": selected_model_name,
                    "reasoning_effort": reasoning_effort,
                    "fallback_used": bool(model_fallback_used),
                    "cost_estimate_usd": cost_estimate_usd,
                },
            )
        return task_id

    async def run_task(
        self,
        *,
        task_prompt: str,
        runner: SubagentRunner,
        parent_session_id: str = "",
        origin_user_id: str = "",
        origin_channel: str = "",
        label: str = "",
        role_key: str = "",
        dispatch_reason: str = "",
        parent_task_id: str = "",
        timeout_seconds: Optional[int] = None,
        write_mode: str = "worktree",
        allowed_paths: Optional[list[str]] = None,
        retry_max_attempts: int = 1,
        retry_backoff_seconds: int = 0,
        selected_model_provider: str = "",
        selected_model_name: str = "",
        reasoning_effort: str = "",
        model_fallback_used: bool = False,
        cost_estimate_usd: Optional[float] = None,
    ) -> SubagentTask:
        """Create and execute one subagent task synchronously."""
        task_id = self._create_task_record(
            task_prompt=task_prompt,
            parent_session_id=parent_session_id,
            origin_user_id=origin_user_id,
            origin_channel=origin_channel,
            label=label,
            role_key=role_key,
            dispatch_reason=dispatch_reason,
            parent_task_id=parent_task_id,
            write_mode=write_mode,
            allowed_paths=allowed_paths,
            retry_max_attempts=retry_max_attempts,
            selected_model_provider=selected_model_provider,
            selected_model_name=selected_model_name,
            reasoning_effort=reasoning_effort,
            model_fallback_used=model_fallback_used,
            cost_estimate_usd=cost_estimate_usd,
        )
        return await self._execute_task(
            task_id=task_id,
            runner=runner,
            timeout_seconds=timeout_seconds,
            retry_max_attempts=retry_max_attempts,
            retry_backoff_seconds=retry_backoff_seconds,
        )

    def submit_task(
        self,
        *,
        task_prompt: str,
        runner: SubagentRunner,
        parent_session_id: str = "",
        origin_user_id: str = "",
        origin_channel: str = "",
        label: str = "",
        role_key: str = "",
        dispatch_reason: str = "",
        parent_task_id: str = "",
        timeout_seconds: Optional[int] = None,
        write_mode: str = "worktree",
        allowed_paths: Optional[list[str]] = None,
        retry_max_attempts: int = 1,
        retry_backoff_seconds: int = 0,
        selected_model_provider: str = "",
        selected_model_name: str = "",
        reasoning_effort: str = "",
        model_fallback_used: bool = False,
        cost_estimate_usd: Optional[float] = None,
    ) -> SubagentTask:
        """Queue one subagent task and return queued snapshot immediately."""
        task_id = self._create_task_record(
            task_prompt=task_prompt,
            parent_session_id=parent_session_id,
            origin_user_id=origin_user_id,
            origin_channel=origin_channel,
            label=label,
            role_key=role_key,
            dispatch_reason=dispatch_reason,
            parent_task_id=parent_task_id,
            write_mode=write_mode,
            allowed_paths=allowed_paths,
            retry_max_attempts=retry_max_attempts,
            selected_model_provider=selected_model_provider,
            selected_model_name=selected_model_name,
            reasoning_effort=reasoning_effort,
            model_fallback_used=model_fallback_used,
            cost_estimate_usd=cost_estimate_usd,
        )
        with self._queued_executions_lock:
            self._queued_executions[task_id] = _QueuedExecution(
                runner=runner,
                timeout_seconds=timeout_seconds,
                retry_max_attempts=retry_max_attempts,
                retry_backoff_seconds=retry_backoff_seconds,
            )
        asyncio.create_task(
            self._queue_backend.enqueue(task_id),
            name=f"subagent-enqueue-{task_id}",
        )
        self._ensure_dispatch_loop_started()
        snapshot = self._store.get_task(task_id)
        if snapshot is None:
            raise RuntimeError("Task missing after queueing")
        return snapshot

    def get_task(self, task_id: str) -> Optional[SubagentTask]:
        return self._store.get_task(task_id)

    @classmethod
    def cancel_task_tree_for_store(
        cls,
        task_id: str,
        store: TaskStore,
    ) -> list[str]:
        all_ids = [task_id] + store.get_descendant_task_ids(task_id)
        cancelled: list[str] = []
        for current_id in all_ids:
            running = cls._get_running_task(current_id)
            if running is not None and not running.done():
                running.cancel()
            snapshot = store.cancel_task(current_id)
            if snapshot is not None:
                cancelled.append(current_id)
        return cancelled

    def cancel_task_tree(self, task_id: str) -> list[str]:
        return self.cancel_task_tree_for_store(task_id, self._store)

    async def _dispatch_loop(self) -> None:
        while True:
            task_id = await self._queue_backend.dequeue()
            if task_id is None:
                return
            with self._queued_executions_lock:
                queued = self._queued_executions.pop(task_id, None)
            if queued is None:
                continue
            execution = asyncio.create_task(
                self._execute_task(
                    task_id=task_id,
                    runner=queued.runner,
                    timeout_seconds=queued.timeout_seconds,
                    retry_max_attempts=queued.retry_max_attempts,
                    retry_backoff_seconds=queued.retry_backoff_seconds,
                ),
                name=f"subagent-task-{task_id}",
            )
            self._set_running_task(task_id, execution)
            execution.add_done_callback(
                lambda _done, tid=task_id: self._clear_running_task(tid),
            )

    def _ensure_dispatch_loop_started(self) -> None:
        with self._dispatch_loop_lock:
            if (
                self._dispatch_loop_task is None
                or self._dispatch_loop_task.done()
            ):
                self._dispatch_loop_task = asyncio.create_task(
                    self._dispatch_loop(),
                    name="subagent-dispatch-loop",
                )

    async def _execute_task(
        self,
        *,
        task_id: str,
        runner: SubagentRunner,
        timeout_seconds: Optional[int],
        retry_max_attempts: int,
        retry_backoff_seconds: int,
    ) -> SubagentTask:
        task_timeout = self._resolve_timeout(timeout_seconds)
        max_attempts = max(1, int(retry_max_attempts))
        backoff_seconds = max(0, int(retry_backoff_seconds))

        current_task = asyncio.current_task()
        if current_task is not None:
            self._set_running_task(task_id, current_task)

        try:
            async with self._semaphore:
                for attempt in range(1, max_attempts + 1):
                    if self._is_cancelled(task_id):
                        snapshot = self._store.cancel_task(task_id)
                        if snapshot is None:
                            raise RuntimeError("Task missing during cancel")
                        return snapshot

                    self._store.set_attempt(task_id, attempt)
                    self._store.set_status(task_id, "running")

                    try:
                        result_text = await asyncio.wait_for(
                            runner(),
                            timeout=task_timeout,
                        )
                        snapshot = self._store.set_status(
                            task_id,
                            "success",
                            result_summary=result_text.strip(),
                        )
                        if snapshot is None:
                            raise RuntimeError(
                                "Task missing after success update",
                            )
                        return snapshot
                    except asyncio.CancelledError:
                        snapshot = self._store.cancel_task(task_id)
                        if snapshot is None:
                            raise RuntimeError(
                                "Task missing after cancellation",
                            )
                        return snapshot
                    except asyncio.TimeoutError:
                        if attempt < max_attempts:
                            if backoff_seconds > 0:
                                await asyncio.sleep(backoff_seconds)
                            continue
                        self._store.append_event(
                            task_id,
                            event_type="error",
                            summary=(
                                "Task timed out after "
                                f"{task_timeout} seconds"
                            ),
                            payload={"attempt": attempt},
                        )
                        snapshot = self._store.set_status(
                            task_id,
                            "timeout",
                            error_message=(
                                "Subagent task timed out after "
                                f"{task_timeout} seconds"
                            ),
                        )
                        if snapshot is None:
                            raise RuntimeError(
                                "Task missing after timeout update",
                            )
                        return snapshot
                    except Exception as exc:  # pylint: disable=broad-except
                        if attempt < max_attempts:
                            if backoff_seconds > 0:
                                await asyncio.sleep(backoff_seconds)
                            continue
                        self._store.append_event(
                            task_id,
                            event_type="error",
                            summary=f"Task failed: {exc}",
                            payload={"attempt": attempt},
                        )
                        snapshot = self._store.set_status(
                            task_id,
                            "error",
                            error_message=str(exc),
                        )
                        if snapshot is None:
                            raise RuntimeError(
                                "Task missing after error update",
                            )
                        return snapshot

                snapshot = self._store.set_status(
                    task_id,
                    "error",
                    error_message=(
                        "Subagent task failed without terminal result"
                    ),
                )
                if snapshot is None:
                    raise RuntimeError("Task missing after terminal failure")
                return snapshot
        finally:
            self._clear_running_task(task_id)

    def _is_cancelled(self, task_id: str) -> bool:
        snapshot = self._store.get_task(task_id)
        return snapshot is not None and snapshot.status == "cancelled"

    def _resolve_timeout(self, requested_timeout: Optional[int]) -> int:
        if requested_timeout is None:
            return self._default_timeout_seconds
        resolved = max(1, int(requested_timeout))
        if resolved > self._hard_timeout_seconds:
            return self._hard_timeout_seconds
        return resolved


def create_subagent_manager(
    config: SubagentsConfig,
    *,
    task_store: Optional[TaskStore] = None,
    queue_backend: Optional[QueueBackend] = None,
    model_router: Optional[ModelRouter] = None,
) -> SubagentManager:
    return SubagentManager(
        max_concurrency=config.max_concurrency,
        default_timeout_seconds=config.default_timeout_seconds,
        hard_timeout_seconds=config.hard_timeout_seconds,
        store=task_store or get_subagent_task_store(),
        queue_backend=queue_backend or InProcQueue(),
        model_router=model_router or LocalModelRouter(),
    )
