from types import SimpleNamespace

from copaw.app.bot_profiles import (
    extract_requested_bot_id,
    namespace_session_id,
    resolve_bot_profile,
)
from copaw.config.config import BotProfileConfig, BotProfilesConfig


def _profiles_config() -> BotProfilesConfig:
    return BotProfilesConfig(
        default_bot="default",
        profiles=[
            BotProfileConfig(key="default", name="Default", enabled=True),
            BotProfileConfig(key="sales", name="Sales", enabled=True),
            BotProfileConfig(key="ops", name="Ops", enabled=False),
        ],
        channel_bindings={"console": "sales"},
    )


def test_extract_requested_bot_id_prefers_direct_field():
    request = SimpleNamespace(
        bot_id="direct_bot",
        channel_meta={"bot_id": "meta_bot"},
    )
    assert extract_requested_bot_id(request) == "direct_bot"


def test_extract_requested_bot_id_reads_channel_meta():
    request = SimpleNamespace(channel_meta={"agent_id": "from_agent_id"})
    assert extract_requested_bot_id(request) == "from_agent_id"


def test_resolve_bot_profile_prefers_explicit_request():
    resolved = resolve_bot_profile(
        profiles_config=_profiles_config(),
        channel="console",
        requested_bot_id="sales",
    )
    assert resolved.key == "sales"
    assert resolved.source == "request.bot_id"


def test_resolve_bot_profile_uses_channel_binding():
    resolved = resolve_bot_profile(
        profiles_config=_profiles_config(),
        channel="console",
        requested_bot_id="",
    )
    assert resolved.key == "sales"
    assert resolved.source == "channel_bindings.console"


def test_resolve_bot_profile_falls_back_to_default_when_binding_disabled():
    cfg = BotProfilesConfig(
        default_bot="default",
        profiles=[
            BotProfileConfig(key="default", enabled=True),
            BotProfileConfig(key="ops", enabled=False),
        ],
        channel_bindings={"qq": "ops"},
    )
    resolved = resolve_bot_profile(
        profiles_config=cfg,
        channel="qq",
        requested_bot_id="",
    )
    assert resolved.key == "default"
    assert resolved.source == "default_bot"


def test_namespace_session_id():
    assert namespace_session_id(bot_key="sales", session_id="abc123") == (
        "bot:sales:abc123"
    )
