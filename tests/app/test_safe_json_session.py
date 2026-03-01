from __future__ import annotations

import json
from pathlib import Path

import pytest

from copaw.app.runner.session import SafeJSONSession


class DummyStateModule:
    def __init__(self, initial: dict | None = None) -> None:
        self.state = initial or {"value": 0}

    def state_dict(self):
        return dict(self.state)

    def load_state_dict(self, data):
        self.state = dict(data)


@pytest.mark.asyncio
async def test_load_session_state_recovers_from_corrupt_json(tmp_path):
    session = SafeJSONSession(save_dir=str(tmp_path))
    session_id = "e447f098"
    user_id = "ou_6ea047213d618cc90b166688e447f098"

    save_path = session._get_save_path(session_id=session_id, user_id=user_id)
    with open(save_path, "w", encoding="utf-8") as f:
        f.write('{"agent": {"name": "Friday", "broken": }')

    agent = DummyStateModule({"value": 42})

    await session.load_session_state(
        session_id=session_id,
        user_id=user_id,
        agent=agent,
    )

    assert agent.state == {"value": 42}
    assert any(tmp_path.glob("*.corrupt-*.json"))
    assert not Path(save_path).exists()


@pytest.mark.asyncio
async def test_save_session_state_writes_valid_json(tmp_path):
    session = SafeJSONSession(save_dir=str(tmp_path))
    session_id = "s1"
    user_id = "u1"
    agent = DummyStateModule({"name": "Friday"})

    await session.save_session_state(session_id=session_id, user_id=user_id, agent=agent)

    save_path = session._get_save_path(session_id=session_id, user_id=user_id)
    with open(save_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["agent"] == {"name": "Friday"}
    assert not list(tmp_path.glob("*.tmp"))
