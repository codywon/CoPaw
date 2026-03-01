# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional

from ...config import SubagentRoleConfig
from .protocols import ModelPlan, ModelTarget


def _parse_fallback_target(
    raw: str,
    primary_provider: str,
) -> Optional[ModelTarget]:
    text = raw.strip()
    if not text:
        return None
    if "/" in text:
        provider, model = text.split("/", 1)
        provider = provider.strip()
        model = model.strip()
        if provider and model:
            return ModelTarget(provider=provider, model=model)
        return None
    if not primary_provider:
        return None
    return ModelTarget(provider=primary_provider, model=text)


class LocalModelRouter:
    """Select a primary model and fallback chain from role policy."""

    def select(
        self,
        role: Optional[SubagentRoleConfig],
        task_ctx: dict,
    ) -> ModelPlan:
        active_provider = str(task_ctx.get("active_provider", "")).strip()
        active_model = str(task_ctx.get("active_model", "")).strip()

        role_provider = role.model_provider.strip() if role is not None else ""
        role_model = role.model_name.strip() if role is not None else ""
        primary_provider = role_provider or active_provider
        primary_model = role_model or active_model
        primary = ModelTarget(provider=primary_provider, model=primary_model)

        seen: set[tuple[str, str]] = {
            (primary.provider.lower(), primary.model.lower()),
        }
        fallbacks: list[ModelTarget] = []
        if role is not None:
            for raw in role.fallback_models:
                target = _parse_fallback_target(raw, primary.provider)
                if target is None:
                    continue
                key = (target.provider.lower(), target.model.lower())
                if key in seen:
                    continue
                seen.add(key)
                fallbacks.append(target)

        return ModelPlan(
            primary=primary,
            fallbacks=fallbacks,
            max_tokens=role.max_tokens if role is not None else None,
            reasoning_effort=(
                role.reasoning_effort.strip() if role is not None else ""
            ),
        )
