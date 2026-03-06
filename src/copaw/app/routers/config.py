# -*- coding: utf-8 -*-

import logging
from typing import Any, List

from fastapi import APIRouter, Body, HTTPException, Path, Request
from pydantic import BaseModel
from ...config import (
    load_config,
    save_config,
    get_heartbeat_config,
    ChannelConfig,
    ChannelConfigUnion,
    get_available_channels,
)
from ..channels.registry import BUILTIN_CHANNEL_KEYS
from ...config.config import HeartbeatConfig

from .schemas_config import HeartbeatBody

router = APIRouter(prefix="/config", tags=["config"])
logger = logging.getLogger(__name__)


class ShowToolDetailsConfig(BaseModel):
    """Global channel rendering option for tool call details."""

    show_tool_details: bool = True


@router.get(
    "/channels",
    summary="List all channels",
    description="Retrieve configuration for all available channels",
)
async def list_channels() -> dict:
    """List all channel configs (filtered by available channels)."""
    config = load_config()
    available = get_available_channels()

    # Get all channel configs from model_dump and __pydantic_extra__
    all_configs = config.channels.model_dump()
    extra = getattr(config.channels, "__pydantic_extra__", None) or {}
    all_configs.update(extra)

    # Return all available channels (use default config if not saved)
    result = {}
    for key in available:
        if key in all_configs:
            channel_data = (
                dict(all_configs[key])
                if isinstance(all_configs[key], dict)
                else all_configs[key]
            )
        else:
            # Channel registered but no config saved yet, use empty default
            channel_data = {"enabled": False, "bot_prefix": ""}
        if isinstance(channel_data, dict):
            channel_data["isBuiltin"] = key in BUILTIN_CHANNEL_KEYS
        result[key] = channel_data

    return result


@router.get(
    "/channels/types",
    summary="List channel types",
    description="Return all available channel type identifiers",
)
async def list_channel_types() -> List[str]:
    """Return available channel type identifiers (env-filtered)."""
    return list(get_available_channels())


@router.put(
    "/channels",
    response_model=ChannelConfig,
    summary="Update all channels",
    description="Update configuration for all channels at once",
)
async def put_channels(
    channels_config: ChannelConfig = Body(
        ...,
        description="Complete channel configuration",
    ),
) -> ChannelConfig:
    """Update all channel configs."""
    config = load_config()
    config.channels = channels_config
    save_config(config)
    return channels_config


@router.get(
    "/channels/{channel_name}",
    response_model=ChannelConfigUnion,
    summary="Get channel config",
    description="Retrieve configuration for a specific channel by name",
)
async def get_channel(
    channel_name: str = Path(
        ...,
        description="Name of the channel to retrieve",
        min_length=1,
    ),
) -> ChannelConfigUnion:
    """Get a specific channel config by name."""
    available = get_available_channels()
    if channel_name not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_name}' not found",
        )
    config = load_config()
    single_channel_config = config.channels.get_channel_config(channel_name)
    if single_channel_config is None:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_name}' not found",
        )
    return single_channel_config


@router.put(
    "/channels/{channel_name}",
    response_model=ChannelConfigUnion,
    summary="Update channel config",
    description="Update configuration for a specific channel by name",
)
async def put_channel(
    channel_name: str = Path(
        ...,
        description="Name of the channel to update",
        min_length=1,
    ),
    single_channel_config: ChannelConfigUnion = Body(
        ...,
        description="Updated channel configuration",
    ),
) -> ChannelConfigUnion:
    """Update a specific channel config by name."""
    available = get_available_channels()
    if channel_name not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Channel '{channel_name}' not found",
        )
    config = load_config()

    # Allow setting extra (plugin) channel config
    setattr(config.channels, channel_name, single_channel_config)
    save_config(config)
    return single_channel_config


@router.get(
    "/show-tool-details",
    response_model=ShowToolDetailsConfig,
    summary="Get tool detail render config",
    description="Return whether tool execution details are shown in channels",
)
async def get_show_tool_details() -> ShowToolDetailsConfig:
    """Get global show_tool_details flag."""
    config = load_config()
    return ShowToolDetailsConfig(show_tool_details=config.show_tool_details)


@router.put(
    "/show-tool-details",
    response_model=ShowToolDetailsConfig,
    summary="Update tool detail render config",
    description="Update whether tool execution details are shown in channels",
)
async def put_show_tool_details(
    request: Request,
    payload: ShowToolDetailsConfig = Body(
        ...,
        description="Tool details render configuration",
    ),
) -> ShowToolDetailsConfig:
    """Update global show_tool_details flag."""
    config = load_config()
    config.show_tool_details = payload.show_tool_details
    save_config(config)

    channel_manager = getattr(getattr(request, "app", None), "state", None)
    channel_manager = getattr(channel_manager, "channel_manager", None)
    if channel_manager is not None:
        await channel_manager.apply_show_tool_details(
            config.channels,
            config.show_tool_details,
        )

    return ShowToolDetailsConfig(show_tool_details=config.show_tool_details)


@router.get(
    "/heartbeat",
    summary="Get heartbeat config",
    description="Return current heartbeat config (interval, target, etc.)",
)
async def get_heartbeat() -> Any:
    """Return effective heartbeat config (from file or default)."""
    hb = get_heartbeat_config()
    return hb.model_dump(mode="json", by_alias=True)


@router.put(
    "/heartbeat",
    summary="Update heartbeat config",
    description="Update heartbeat and hot-reload the scheduler",
)
async def put_heartbeat(
    request: Request,
    body: HeartbeatBody = Body(..., description="Heartbeat configuration"),
) -> Any:
    """Update heartbeat config and reschedule the heartbeat job."""
    config = load_config()
    hb = HeartbeatConfig(
        enabled=body.enabled,
        every=body.every,
        target=body.target,
        active_hours=body.active_hours,
    )
    config.agents.defaults.heartbeat = hb
    save_config(config)

    cron_manager = getattr(request.app.state, "cron_manager", None)
    if cron_manager is not None:
        await cron_manager.reschedule_heartbeat()

    return hb.model_dump(mode="json", by_alias=True)
