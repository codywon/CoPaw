# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...config import SubagentRoleConfig, SubagentsConfig


@dataclass(frozen=True)
class DispatchDecision:
    should_dispatch: bool
    reason: str = ""


def _normalize_text(value: str) -> str:
    return value.lower().strip()


def should_force_dispatch(
    task_prompt: str,
    config: SubagentsConfig,
) -> DispatchDecision:
    """Return whether the task must be delegated under dispatch policy."""
    if not config.enabled:
        return DispatchDecision(False, "disabled")

    mode = config.dispatch_mode
    if mode == "advisory":
        return DispatchDecision(False, "advisory")
    if mode == "force_by_default":
        return DispatchDecision(True, "force_by_default")

    prompt = task_prompt.strip()
    if not prompt:
        return DispatchDecision(False, "empty_task")

    if len(prompt) >= config.auto_dispatch_min_prompt_chars:
        return DispatchDecision(True, "force_when_matched:length")

    lower_prompt = _normalize_text(prompt)
    for kw in config.auto_dispatch_keywords:
        key = _normalize_text(kw)
        if not key:
            continue
        if key in lower_prompt:
            return DispatchDecision(
                True,
                f"force_when_matched:keyword:{key}",
            )

    return DispatchDecision(False, "force_when_matched:not_matched")


def select_role_for_task(
    task_prompt: str,
    config: SubagentsConfig,
    profile: str = "",
) -> Optional[SubagentRoleConfig]:
    """Pick role by explicit profile, then keyword routing, then default role."""
    profile_key = profile.strip()
    roles = [role for role in config.roles if role.enabled]
    if not roles:
        return None

    if profile_key:
        for role in roles:
            if role.key == profile_key:
                return role
        return None

    default_role = config.default_role.strip()
    if config.role_selection_mode == "default":
        if not default_role:
            return None
        for role in roles:
            if role.key == default_role:
                return role
        return None

    text = _normalize_text(task_prompt)
    best_role: Optional[SubagentRoleConfig] = None
    best_score = 0
    for role in roles:
        score = 0
        for keyword in role.routing_keywords:
            key = _normalize_text(keyword)
            if key and key in text:
                score += 1
        if score > best_score:
            best_role = role
            best_score = score

    if best_role is not None:
        return best_role

    if default_role:
        for role in roles:
            if role.key == default_role:
                return role
    return None
