from __future__ import annotations

import pytest

from copaw.app.channels.feishu.channel import FeishuChannel


async def _dummy_process(_request):
    if False:
        yield None


@pytest.mark.asyncio
async def test_send_text_uses_post_only_when_rendering_text():
    channel = FeishuChannel(
        process=_dummy_process,
        enabled=True,
        app_id="app",
        app_secret="secret",
        bot_prefix="[BOT] ",
    )

    calls: list[str] = []

    def _fake_send_message_sync(
        receive_id_type: str,
        receive_id: str,
        msg_type: str,
        content: str,
    ) -> bool:
        del receive_id_type, receive_id, content
        calls.append(msg_type)
        return True

    channel._send_message_sync = _fake_send_message_sync  # type: ignore[method-assign]

    ok = await channel._send_text("open_id", "ou_xxx", "hello")

    assert ok is True
    assert calls == ["post"]
