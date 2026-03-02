from __future__ import annotations

from typing import Any, Dict, List

import pytest

from copaw.app.crons.executor import CronExecutor
from copaw.app.crons.models import CronJobSpec
from copaw.config.config import Config, LastDispatchConfig


class _Runner:
    def __init__(self) -> None:
        self.requests: List[Dict[str, Any]] = []

    async def stream_query(self, request: Dict[str, Any]):
        self.requests.append(request)
        yield {"type": "final", "content": "ok"}


class _ChannelManager:
    def __init__(self) -> None:
        self.text_calls: List[Dict[str, Any]] = []
        self.event_calls: List[Dict[str, Any]] = []

    async def send_text(
        self,
        *,
        channel: str,
        user_id: str,
        session_id: str,
        text: str,
        meta: Dict[str, Any],
    ) -> None:
        self.text_calls.append(
            {
                "channel": channel,
                "user_id": user_id,
                "session_id": session_id,
                "text": text,
                "meta": meta,
            },
        )

    async def send_event(
        self,
        *,
        channel: str,
        user_id: str,
        session_id: str,
        event: Dict[str, Any],
        meta: Dict[str, Any],
    ) -> None:
        self.event_calls.append(
            {
                "channel": channel,
                "user_id": user_id,
                "session_id": session_id,
                "event": event,
                "meta": meta,
            },
        )


def _base_last_dispatch_config() -> Config:
    cfg = Config()
    cfg.last_dispatch = LastDispatchConfig(
        channel="feishu",
        user_id="ou_test_receiver",
        session_id="abcd1234",
    )
    return cfg


def _make_text_job() -> CronJobSpec:
    return CronJobSpec(
        id="job-text",
        name="weather",
        enabled=True,
        schedule={"type": "cron", "cron": "30 8 * * *", "timezone": "UTC"},
        task_type="text",
        text="today weather",
        dispatch={
            "type": "channel",
            "channel": "feishu",
            "target": {"user_id": "default", "session_id": "feishu:default"},
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


def _make_agent_job() -> CronJobSpec:
    return CronJobSpec(
        id="job-agent",
        name="weather-agent",
        enabled=True,
        schedule={"type": "cron", "cron": "30 8 * * *", "timezone": "UTC"},
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
            "session_id": "feishu:default",
        },
        dispatch={
            "type": "channel",
            "channel": "feishu",
            "target": {"user_id": "default", "session_id": "feishu:default"},
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
async def test_text_job_strict_policy_rejects_placeholder_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "copaw.app.crons.executor.load_config",
        _base_last_dispatch_config,
    )
    runner = _Runner()
    channel_manager = _ChannelManager()
    executor = CronExecutor(runner=runner, channel_manager=channel_manager)

    with pytest.raises(RuntimeError):
        await executor.execute(_make_text_job())


@pytest.mark.asyncio
async def test_agent_job_fallback_policy_resolves_last_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "copaw.app.crons.executor.load_config",
        _base_last_dispatch_config,
    )
    runner = _Runner()
    channel_manager = _ChannelManager()
    executor = CronExecutor(runner=runner, channel_manager=channel_manager)
    payload = _make_agent_job().model_dump(mode="json")
    payload["dispatch"]["target_policy"] = "fallback_last"
    job = CronJobSpec.model_validate(payload)

    await executor.execute(job)

    assert len(runner.requests) == 1
    req = runner.requests[0]
    assert req["user_id"] == "ou_test_receiver"
    assert req["session_id"] == "abcd1234"

    assert len(channel_manager.event_calls) == 1
    call = channel_manager.event_calls[0]
    assert call["user_id"] == "ou_test_receiver"
    assert call["session_id"] == "abcd1234"
    assert call["meta"]["feishu_receive_id_type"] == "open_id"
    assert call["meta"]["feishu_receive_id"] == "ou_test_receiver"
