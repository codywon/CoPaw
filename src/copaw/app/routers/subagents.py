# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query

from ...agents.subagents import (
    SubagentManager,
    SubagentTask,
    SubagentTaskListResponse,
    get_subagent_task_store,
)
from ...config import load_config, save_config, SubagentsConfig

router = APIRouter(prefix="/agent/subagents", tags=["subagents"])


def _validate_subagents_config(config: SubagentsConfig) -> SubagentsConfig:
    if config.hard_timeout_seconds < config.default_timeout_seconds:
        raise HTTPException(
            status_code=400,
            detail=(
                "hard_timeout_seconds must be greater than or equal to "
                "default_timeout_seconds"
            ),
        )

    normalized_paths: list[str] = []
    seen: set[str] = set()
    for path in config.allowed_paths:
        p = path.strip()
        if not p:
            continue
        if p in seen:
            continue
        normalized_paths.append(p)
        seen.add(p)
    config.allowed_paths = normalized_paths

    normalized_keywords: list[str] = []
    seen_keywords: set[str] = set()
    for keyword in config.auto_dispatch_keywords:
        k = keyword.strip()
        if not k:
            continue
        key = k.lower()
        if key in seen_keywords:
            continue
        normalized_keywords.append(k)
        seen_keywords.add(key)
    config.auto_dispatch_keywords = normalized_keywords

    seen_role_keys: set[str] = set()
    normalized_default_role = config.default_role.strip()
    normalized_roles = []
    for role in config.roles:
        key = role.key.strip()
        if not key:
            raise HTTPException(
                status_code=400,
                detail="subagent role key cannot be empty",
            )
        if key in seen_role_keys:
            raise HTTPException(
                status_code=400,
                detail=f"duplicate subagent role key: {key}",
            )
        seen_role_keys.add(key)
        role.key = key
        role.name = role.name.strip() or key
        role.description = role.description.strip()
        role.identity_prompt = role.identity_prompt.strip()
        role.tool_guidelines = role.tool_guidelines.strip()

        normalized_role_keywords: list[str] = []
        seen_role_keywords: set[str] = set()
        for keyword in role.routing_keywords:
            kw = keyword.strip()
            if not kw:
                continue
            lower_kw = kw.lower()
            if lower_kw in seen_role_keywords:
                continue
            normalized_role_keywords.append(kw)
            seen_role_keywords.add(lower_kw)
        role.routing_keywords = normalized_role_keywords
        normalized_roles.append(role)

    if normalized_default_role and normalized_default_role not in seen_role_keys:
        raise HTTPException(
            status_code=400,
            detail=(
                "default_role must match one of configured roles "
                "when it is not empty"
            ),
        )
    config.default_role = normalized_default_role
    config.roles = normalized_roles
    return config


@router.get(
    "/config",
    response_model=SubagentsConfig,
    summary="Get subagents config",
)
async def get_subagents_config() -> SubagentsConfig:
    conf = load_config()
    return conf.agents.subagents


@router.put(
    "/config",
    response_model=SubagentsConfig,
    summary="Update subagents config",
)
async def put_subagents_config(
    subagents_config: SubagentsConfig = Body(
        ...,
        description="Updated subagents configuration",
    ),
) -> SubagentsConfig:
    validated = _validate_subagents_config(subagents_config)
    conf = load_config()
    conf.agents.subagents = validated
    save_config(conf)
    return validated


@router.get(
    "/tasks",
    response_model=SubagentTaskListResponse,
    summary="List subagent tasks",
)
async def list_subagent_tasks(
    status: Optional[str] = Query(
        default=None,
        description="Filter by task status",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> SubagentTaskListResponse:
    store = get_subagent_task_store()
    tasks = store.list_tasks()
    if status:
        tasks = [task for task in tasks if task.status == status]

    def _sort_key(task: SubagentTask) -> float:
        ref = task.started_at or task.ended_at
        return ref.timestamp() if ref is not None else 0.0

    tasks.sort(
        key=_sort_key,
        reverse=True,
    )
    total = len(tasks)
    page = tasks[offset : offset + limit]
    return SubagentTaskListResponse(
        items=page,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/tasks/{task_id}",
    response_model=SubagentTask,
    summary="Get subagent task detail",
)
async def get_subagent_task(
    task_id: str = Path(..., min_length=1),
) -> SubagentTask:
    store = get_subagent_task_store()
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Subagent task not found")
    return task


@router.post(
    "/tasks/{task_id}/cancel",
    response_model=SubagentTask,
    summary="Cancel subagent task",
)
async def cancel_subagent_task(
    task_id: str = Path(..., min_length=1),
) -> SubagentTask:
    store = get_subagent_task_store()
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Subagent task not found")
    if task.status in {"success", "error", "timeout", "cancelled"}:
        raise HTTPException(
            status_code=409,
            detail=f"Subagent task cannot be cancelled in status '{task.status}'",
        )

    cancelled_ids = SubagentManager.cancel_task_tree_for_store(task_id, store)
    if not cancelled_ids:
        raise HTTPException(status_code=404, detail="Subagent task not found")
    cancelled = store.get_task(task_id)
    if cancelled is None:
        raise HTTPException(status_code=404, detail="Subagent task not found")
    return cancelled
