# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import threading
from typing import Awaitable, Callable, Optional

from .models import SubagentTask
from .store import InMemorySubagentTaskStore, get_subagent_task_store

SubagentRunner = Callable[[], Awaitable[str]]


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
        store: Optional[InMemorySubagentTaskStore] = None,
    ) -> None:
        self._max_concurrency = max(1, max_concurrency)
        self._semaphore = self._get_global_semaphore(self._max_concurrency)
        self._default_timeout_seconds = max(1, default_timeout_seconds)
        self._hard_timeout_seconds = max(
            self._default_timeout_seconds,
            hard_timeout_seconds,
        )
        self._store = store or get_subagent_task_store()

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
    ) -> str:
        return self._store.create_task(
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
        )

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
        )
        bg_task = asyncio.create_task(
            self._execute_task(
                task_id=task_id,
                runner=runner,
                timeout_seconds=timeout_seconds,
                retry_max_attempts=retry_max_attempts,
                retry_backoff_seconds=retry_backoff_seconds,
            ),
            name=f"subagent-task-{task_id}",
        )
        self._set_running_task(task_id, bg_task)
        bg_task.add_done_callback(lambda _: self._clear_running_task(task_id))
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
        store: InMemorySubagentTaskStore,
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
                            raise RuntimeError("Task missing after success update")
                        return snapshot
                    except asyncio.CancelledError:
                        snapshot = self._store.cancel_task(task_id)
                        if snapshot is None:
                            raise RuntimeError("Task missing after cancellation")
                        return snapshot
                    except asyncio.TimeoutError:
                        if attempt < max_attempts:
                            if backoff_seconds > 0:
                                await asyncio.sleep(backoff_seconds)
                            continue
                        snapshot = self._store.set_status(
                            task_id,
                            "timeout",
                            error_message=(
                                "Subagent task timed out after "
                                f"{task_timeout} seconds"
                            ),
                        )
                        if snapshot is None:
                            raise RuntimeError("Task missing after timeout update")
                        return snapshot
                    except Exception as exc:  # pylint: disable=broad-except
                        if attempt < max_attempts:
                            if backoff_seconds > 0:
                                await asyncio.sleep(backoff_seconds)
                            continue
                        snapshot = self._store.set_status(
                            task_id,
                            "error",
                            error_message=str(exc),
                        )
                        if snapshot is None:
                            raise RuntimeError("Task missing after error update")
                        return snapshot

                snapshot = self._store.set_status(
                    task_id,
                    "error",
                    error_message="Subagent task failed without terminal result",
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
