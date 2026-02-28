import asyncio
import time

import pytest

from copaw.agents.subagents import get_subagent_task_store
from copaw.agents.subagents.manager import SubagentManager


@pytest.mark.asyncio
async def test_manager_runs_task_successfully():
    manager = SubagentManager(
        max_concurrency=2,
        default_timeout_seconds=30,
        hard_timeout_seconds=60,
    )

    async def _runner():
        return "done"

    task = await manager.run_task(
        task_prompt="test task",
        runner=_runner,
        parent_session_id="s1",
    )
    assert task.status == "success"
    assert task.result_summary == "done"


@pytest.mark.asyncio
async def test_manager_marks_timeout():
    manager = SubagentManager(
        max_concurrency=1,
        default_timeout_seconds=1,
        hard_timeout_seconds=2,
    )

    async def _runner():
        await asyncio.sleep(2)
        return "done"

    task = await manager.run_task(
        task_prompt="slow task",
        runner=_runner,
        timeout_seconds=1,
    )
    assert task.status == "timeout"


@pytest.mark.asyncio
async def test_manager_shared_global_concurrency_across_instances():
    manager_a = SubagentManager(
        max_concurrency=1,
        default_timeout_seconds=30,
        hard_timeout_seconds=60,
    )
    manager_b = SubagentManager(
        max_concurrency=1,
        default_timeout_seconds=30,
        hard_timeout_seconds=60,
    )

    async def _runner():
        await asyncio.sleep(0.2)
        return "ok"

    start = time.perf_counter()
    await asyncio.gather(
        manager_a.run_task(task_prompt="task-a", runner=_runner),
        manager_b.run_task(task_prompt="task-b", runner=_runner),
    )
    elapsed = time.perf_counter() - start
    assert elapsed >= 0.35


@pytest.mark.asyncio
async def test_manager_submit_task_runs_in_background():
    manager = SubagentManager(
        max_concurrency=2,
        default_timeout_seconds=30,
        hard_timeout_seconds=60,
    )

    async def _runner():
        await asyncio.sleep(0.05)
        return "bg-ok"

    queued = manager.submit_task(
        task_prompt="background",
        runner=_runner,
    )
    assert queued.status == "queued"

    await asyncio.sleep(0.15)
    latest = manager.get_task(queued.task_id)
    assert latest is not None
    assert latest.status == "success"
    assert latest.result_summary == "bg-ok"


@pytest.mark.asyncio
async def test_manager_retries_then_succeeds():
    manager = SubagentManager(
        max_concurrency=1,
        default_timeout_seconds=30,
        hard_timeout_seconds=60,
    )
    attempt = {"count": 0}

    async def _runner():
        attempt["count"] += 1
        if attempt["count"] < 2:
            raise RuntimeError("first-fail")
        return "ok-after-retry"

    task = await manager.run_task(
        task_prompt="retry-task",
        runner=_runner,
        retry_max_attempts=2,
        retry_backoff_seconds=0,
    )
    assert task.status == "success"
    assert task.attempts == 2
    assert task.max_attempts == 2
    assert task.result_summary == "ok-after-retry"


@pytest.mark.asyncio
async def test_manager_cancel_task_tree_cascades_to_children():
    store = get_subagent_task_store()
    manager = SubagentManager(
        max_concurrency=1,
        default_timeout_seconds=30,
        hard_timeout_seconds=60,
        store=store,
    )

    async def _runner():
        await asyncio.sleep(5)
        return "never"

    parent = manager.submit_task(
        task_prompt="parent",
        runner=_runner,
    )
    child = store.create_task(
        parent_session_id="",
        parent_task_id=parent.task_id,
        task_prompt="child",
    )
    store.set_status(child, "running")

    await asyncio.sleep(0.1)
    cancelled_ids = manager.cancel_task_tree(parent.task_id)
    assert parent.task_id in cancelled_ids
    assert child in cancelled_ids

    await asyncio.sleep(0.1)
    p = store.get_task(parent.task_id)
    c = store.get_task(child)
    assert p is not None and p.status == "cancelled"
    assert c is not None and c.status == "cancelled"
