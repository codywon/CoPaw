from __future__ import annotations

from types import SimpleNamespace

import pytest

from copaw.app.channels.feishu.channel import FeishuChannel


async def _dummy_process(_request):
    if False:
        yield None


@pytest.mark.asyncio
async def test_part_to_file_path_or_url_accepts_video_url_local_path(tmp_path):
    channel = FeishuChannel(
        process=_dummy_process,
        enabled=True,
        app_id="app",
        app_secret="secret",
        bot_prefix="[BOT] ",
    )

    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"fake-mp4")

    part = SimpleNamespace(
        type="video",
        video_url=str(video_path),
        file_url=None,
        image_url=None,
        data=None,
        filename="sample.mp4",
    )

    out = await channel._part_to_file_path_or_url(part)

    assert out == str(video_path)


@pytest.mark.asyncio
async def test_part_to_file_path_or_url_accepts_video_url_http():
    channel = FeishuChannel(
        process=_dummy_process,
        enabled=True,
        app_id="app",
        app_secret="secret",
        bot_prefix="[BOT] ",
    )

    part = SimpleNamespace(
        type="video",
        video_url="https://example.com/a.mp4",
        file_url=None,
        image_url=None,
        data=None,
        filename="a.mp4",
    )

    out = await channel._part_to_file_path_or_url(part)

    assert out == "https://example.com/a.mp4"
