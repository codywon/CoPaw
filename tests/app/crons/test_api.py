from __future__ import annotations

from fastapi import HTTPException

import pytest

from copaw.app.crons.api import _normalize_spec_for_save
from copaw.app.crons.models import CronJobSpec
from copaw.config.config import Config, LastDispatchConfig


def _make_agent_job_with_placeholder_target() -> CronJobSpec:
    return CronJobSpec(
        id="job-agent",
        name="daily-weather",
        enabled=True,
        schedule={
            "type": "cron",
            "cron": "30 8 * * *",
            "timezone": "Asia/Shanghai",
        },
        task_type="agent",
        request={
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": "weather"}],
                },
            ],
            "user_id": "default",
            "session_id": "default",
        },
        dispatch={
            "type": "channel",
            "channel": "feishu",
            "target": {
                "user_id": "default",
                "session_id": "default",
            },
            "mode": "final",
            "meta": {},
        },
        runtime={
            "max_concurrency": 1,
            "timeout_seconds": 120,
            "misfire_grace_seconds": 60,
        },
        meta={},
    )


def test_normalize_spec_for_save_binds_target_from_last_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = Config()
    cfg.last_dispatch = LastDispatchConfig(
        channel="feishu",
        user_id="ou_abc123",
        session_id="e447f098",
    )
    monkeypatch.setattr("copaw.app.crons.api.load_config", lambda: cfg)

    normalized = _normalize_spec_for_save(
        _make_agent_job_with_placeholder_target(),
    )

    assert normalized.dispatch.target.user_id == "ou_abc123"
    assert normalized.dispatch.target.session_id == "e447f098"
    assert normalized.request is not None
    assert normalized.request.user_id == "ou_abc123"
    assert normalized.request.session_id == "e447f098"
    assert normalized.dispatch.meta["feishu_receive_id"] == "ou_abc123"
    assert (
        normalized.dispatch.meta["feishu_receive_id_type"] == "open_id"
    )


def test_normalize_spec_for_save_raises_when_strict_target_unresolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("copaw.app.crons.api.load_config", Config)

    with pytest.raises(HTTPException) as exc:
        _normalize_spec_for_save(_make_agent_job_with_placeholder_target())

    assert exc.value.status_code == 400
    assert "定时任务目标未绑定" in str(exc.value.detail)
