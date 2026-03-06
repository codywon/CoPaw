import pytest
from pydantic import ValidationError

from copaw.config.config import (
    AgentsConfig,
    BotProfileConfig,
    BotProfilesConfig,
)


def test_bot_profiles_defaults_loaded():
    cfg = AgentsConfig()
    assert cfg.bot_profiles.enabled is True
    assert cfg.bot_profiles.default_bot == "default"
    assert len(cfg.bot_profiles.profiles) == 1
    assert cfg.bot_profiles.profiles[0].key == "default"
    assert cfg.bot_profiles.profiles[0].enabled is True


def test_bot_profiles_duplicate_keys_rejected():
    with pytest.raises(ValidationError):
        BotProfilesConfig(
            profiles=[
                BotProfileConfig(key="sales", enabled=True),
                BotProfileConfig(key="Sales", enabled=True),
            ],
            default_bot="sales",
        )


def test_bot_profiles_default_bot_must_be_enabled():
    with pytest.raises(ValidationError):
        BotProfilesConfig(
            profiles=[
                BotProfileConfig(key="default", enabled=False),
                BotProfileConfig(key="ops", enabled=True),
            ],
            default_bot="default",
        )


def test_bot_profiles_channel_bindings_filtered_by_existing_profiles():
    cfg = BotProfilesConfig(
        profiles=[
            BotProfileConfig(key="default", enabled=True),
            BotProfileConfig(key="ops", enabled=True),
        ],
        default_bot="default",
        channel_bindings={
            "console": "ops",
            "qq": "missing_profile",
        },
    )
    assert cfg.channel_bindings == {"console": "ops"}
