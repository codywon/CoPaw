# -*- coding: utf-8 -*-
from copaw.config.config import Config
from copaw.config.utils import get_channel_instances


def test_get_channel_instances_includes_valid_extra_instances():
    config = Config.model_validate(
        {
            "channels": {
                "console": {
                    "enabled": True,
                    "bot_prefix": "[BOT] ",
                },
                "console_sales": {
                    "channel_type": "console",
                    "enabled": True,
                    "bot_prefix": "[Sales] ",
                },
            },
        },
    )

    instances = get_channel_instances(config.channels)

    assert "console" in instances
    assert instances["console"]["channel_type"] == "console"
    assert "console_sales" in instances
    assert instances["console_sales"]["channel_type"] == "console"


def test_get_channel_instances_ignores_invalid_extra_entries():
    config = Config.model_validate(
        {
            "channels": {
                "console": {
                    "enabled": True,
                    "bot_prefix": "[BOT] ",
                },
                "bad_type": {
                    "channel_type": "unknown",
                    "enabled": True,
                },
                "missing_type": {
                    "enabled": True,
                },
                "not_a_dict": "skip",
            },
        },
    )

    instances = get_channel_instances(config.channels)

    assert "console" in instances
    assert "bad_type" not in instances
    assert "missing_type" not in instances
    assert "not_a_dict" not in instances
