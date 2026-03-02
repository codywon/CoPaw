# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ...config.config import LastDispatchConfig

_PLACEHOLDER_TARGET_VALUES = {"", "default", "cron"}


def is_placeholder_target(user_id: str, session_id: str) -> bool:
    user = (user_id or "").strip().lower()
    session = (session_id or "").strip().lower()
    if user in _PLACEHOLDER_TARGET_VALUES:
        return True
    if session in _PLACEHOLDER_TARGET_VALUES:
        return True
    return session.startswith("feishu:") and session.endswith("default")


def _resolve_from_last_dispatch(
    *,
    channel: str,
    user_id: str,
    session_id: str,
    last_dispatch: Optional[LastDispatchConfig],
) -> Optional[Tuple[str, str]]:
    if last_dispatch is None:
        return None
    if last_dispatch.channel != channel:
        return None
    if not (last_dispatch.user_id or last_dispatch.session_id):
        return None
    out_user_id = (last_dispatch.user_id or user_id).strip()
    out_session_id = (last_dispatch.session_id or session_id).strip()
    return out_user_id, out_session_id


def resolve_target_for_persist(
    *,
    channel: str,
    user_id: str,
    session_id: str,
    target_policy: str,
    last_dispatch: Optional[LastDispatchConfig],
) -> Tuple[str, str]:
    if not is_placeholder_target(user_id, session_id):
        return (user_id, session_id)
    resolved = _resolve_from_last_dispatch(
        channel=channel,
        user_id=user_id,
        session_id=session_id,
        last_dispatch=last_dispatch,
    )
    if resolved is not None:
        return resolved
    if target_policy == "strict":
        raise ValueError(
            f"定时任务目标未绑定（channel={channel}）。"
            "请先在该渠道给机器人发一条消息完成自动绑定，"
            "或在任务里显式填写 target.user_id / target.session_id。",
        )
    return (user_id, session_id)


def resolve_target_for_execute(
    *,
    channel: str,
    user_id: str,
    session_id: str,
    target_policy: str,
    last_dispatch: Optional[LastDispatchConfig],
) -> Tuple[str, str]:
    if not is_placeholder_target(user_id, session_id):
        return (user_id, session_id)
    if target_policy == "fallback_last":
        resolved = _resolve_from_last_dispatch(
            channel=channel,
            user_id=user_id,
            session_id=session_id,
            last_dispatch=last_dispatch,
        )
        if resolved is not None:
            return resolved
        return (user_id, session_id)
    raise RuntimeError(
        f"严格投递模式阻止了占位目标（channel={channel}）。"
        "请在创建/更新任务时完成目标绑定。",
    )


def enrich_dispatch_meta(
    *,
    channel: str,
    user_id: str,
    meta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    out: Dict[str, Any] = dict(meta or {})
    if channel != "feishu":
        return out
    if out.get("feishu_receive_id"):
        return out
    uid = (user_id or "").strip()
    if uid.startswith("ou_"):
        out["feishu_receive_id"] = uid
        out.setdefault("feishu_receive_id_type", "open_id")
    return out
