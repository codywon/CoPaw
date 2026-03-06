# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..config import BotProfileConfig, BotProfilesConfig


@dataclass(frozen=True)
class ResolvedBotProfile:
    key: str
    name: str
    identity_prompt: str
    source: str


def _normalize(value: Optional[str]) -> str:
    return (value or "").strip()


def extract_requested_bot_id(request) -> str:
    """Extract explicit bot id from request extensions/meta if present."""
    direct_bot_id = _normalize(getattr(request, "bot_id", ""))
    if direct_bot_id:
        return direct_bot_id

    channel_meta = getattr(request, "channel_meta", None) or {}
    if isinstance(channel_meta, dict):
        for key in ("bot_id", "bot_key", "agent_id"):
            value = _normalize(channel_meta.get(key))
            if value:
                return value
    return ""


def namespace_session_id(*, bot_key: str, session_id: str) -> str:
    """Build session namespace key for bot-isolated chat context."""
    sid = _normalize(session_id) or "default"
    return f"bot:{bot_key}:{sid}"


def resolve_bot_profile(
    *,
    profiles_config: BotProfilesConfig,
    channel: str,
    requested_bot_id: str = "",
) -> ResolvedBotProfile:
    """Resolve bot profile by explicit request, channel binding, then default."""
    profile_by_key: dict[str, BotProfileConfig] = {}
    for profile in profiles_config.profiles:
        profile_by_key[profile.key.lower()] = profile

    enabled_profiles = [
        profile
        for profile in profiles_config.profiles
        if profile.enabled
    ]
    fallback_profile = (
        enabled_profiles[0] if enabled_profiles else profiles_config.profiles[0]
    )

    requested = _normalize(requested_bot_id).lower()
    if requested:
        profile = profile_by_key.get(requested)
        if profile is not None and profile.enabled:
            return ResolvedBotProfile(
                key=profile.key,
                name=profile.name or profile.key,
                identity_prompt=profile.identity_prompt,
                source="request.bot_id",
            )

    channel_key = _normalize(channel)
    bound_key = _normalize(profiles_config.channel_bindings.get(channel_key, ""))
    if bound_key:
        profile = profile_by_key.get(bound_key.lower())
        if profile is not None and profile.enabled:
            return ResolvedBotProfile(
                key=profile.key,
                name=profile.name or profile.key,
                identity_prompt=profile.identity_prompt,
                source=f"channel_bindings.{channel_key}",
            )

    default_key = profiles_config.default_bot.lower()
    default_profile = profile_by_key.get(default_key)
    if default_profile is not None and default_profile.enabled:
        return ResolvedBotProfile(
            key=default_profile.key,
            name=default_profile.name or default_profile.key,
            identity_prompt=default_profile.identity_prompt,
            source="default_bot",
        )

    return ResolvedBotProfile(
        key=fallback_profile.key,
        name=fallback_profile.name or fallback_profile.key,
        identity_prompt=fallback_profile.identity_prompt,
        source="fallback_enabled_profile",
    )
