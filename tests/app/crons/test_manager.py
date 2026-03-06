from __future__ import annotations

from datetime import datetime, timezone

import pytest

from copaw.app.crons.manager import CronManager
from copaw.app.crons.models import CronJobSpec


class _Repo:
    def __init__(self, job: CronJobSpec):
        self._job = job

    async def get_job(self, job_id: str):
        if job_id == self._job.id:
            return self._job
        return None


class _ApsJob:
    def __init__(self, next_run_time: datetime):
        self.next_run_time = next_run_time


class _Scheduler:
    def __init__(self, next_run_time: datetime):
        self._job = _ApsJob(next_run_time)

    def get_job(self, _job_id: str):
        return self._job


def _make_agent_job() -> CronJobSpec:
    return CronJobSpec(
        id="job-manager",
        name="manager-test",
        enabled=True,
        schedule={"type": "cron", "cron": "30 8 * * *", "timezone": "UTC"},
        task_type="agent",
        request={
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "hello"}],
                },
            ],
            "user_id": "default",
            "session_id": "default",
        },
        dispatch={
            "type": "channel",
            "channel": "console",
            "target": {"user_id": "default", "session_id": "default"},
            "mode": "final",
            "meta": {},
        },
        runtime={
            "max_concurrency": 1,
            "timeout_seconds": 30,
            "misfire_grace_seconds": 60,
        },
        meta={},
    )


@pytest.mark.asyncio
async def test_scheduled_callback_updates_next_run_even_when_execute_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = _make_agent_job()
    repo = _Repo(job)
    mgr = CronManager(repo=repo, runner=object(), channel_manager=object())
    next_run = datetime(2026, 3, 4, 9, 0, tzinfo=timezone.utc)
    mgr._scheduler = _Scheduler(next_run)

    async def _boom(_job):
        raise RuntimeError("boom")

    monkeypatch.setattr(mgr, "_execute_once", _boom)

    with pytest.raises(RuntimeError):
        await mgr._scheduled_callback(job.id)

    state = mgr.get_state(job.id)
    assert state.next_run_at == next_run
