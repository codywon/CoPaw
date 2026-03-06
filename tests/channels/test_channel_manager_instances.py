# -*- coding: utf-8 -*-
import pytest

from copaw.app.channels.manager import ChannelManager
from copaw.config.config import Config


async def _dummy_process(_request):
    if False:
        yield None


def _build_config_with_console_instances() -> Config:
    return Config.model_validate(
        {
            "channels": {
                "console": {
                    "enabled": True,
                    "bot_prefix": "[Default] ",
                },
                "console_sales": {
                    "channel_type": "console",
                    "enabled": True,
                    "bot_prefix": "[Sales] ",
                },
            },
        },
    )


def test_channel_manager_from_config_builds_multiple_same_type_instances():
    manager = ChannelManager.from_config(
        process=_dummy_process,
        config=_build_config_with_console_instances(),
    )

    names = {channel.channel for channel in manager.channels}
    assert "console" in names
    assert "console_sales" in names

    sales = next(
        channel for channel in manager.channels if channel.channel == "console_sales"
    )
    assert getattr(sales, "_channel_type", "") == "console"
    assert getattr(sales, "bot_prefix", "") == "[Sales] "


@pytest.mark.asyncio
async def test_channel_manager_can_remove_channel_instance():
    manager = ChannelManager.from_config(
        process=_dummy_process,
        config=_build_config_with_console_instances(),
    )

    assert await manager.get_channel("console_sales") is not None
    await manager.remove_channel("console_sales")
    assert await manager.get_channel("console_sales") is None
