# -*- coding: utf-8 -*-
"""Watch config.json for changes and auto-reload channels."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from .utils import (
    load_config,
    get_config_path,
    get_channel_instances,
)
from .config import ChannelConfig
from ..app.channels import ChannelManager  # pylint: disable=no-name-in-module

logger = logging.getLogger(__name__)

# How often to poll (seconds)
DEFAULT_POLL_INTERVAL = 2.0


class ConfigWatcher:
    """Poll config.json mtime; reload only changed channels automatically."""

    def __init__(
        self,
        channel_manager: ChannelManager,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        config_path: Optional[Path] = None,
    ):
        self._channel_manager = channel_manager
        self._poll_interval = poll_interval
        self._config_path = config_path or get_config_path()
        self._task: Optional[asyncio.Task] = None

        # Snapshot of the last known channel config (for diffing)
        self._last_channels: Optional[ChannelConfig] = None
        self._last_channels_hash: Optional[int] = None
        self._last_show_tool_details: Optional[bool] = None
        self._last_show_reasoning: Optional[bool] = None
        # mtime of config.json at last check
        self._last_mtime: float = 0.0

    async def start(self) -> None:
        """Take initial snapshot and start the polling task."""
        self._snapshot()
        self._task = asyncio.create_task(
            self._poll_loop(),
            name="config_watcher",
        )
        logger.info(
            "ConfigWatcher started (poll=%.1fs, path=%s)",
            self._poll_interval,
            self._config_path,
        )

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("ConfigWatcher stopped")

    # ------------------------------------------------------------------

    def _snapshot(self) -> None:
        """Load current config and record mtime + channels hash."""
        try:
            self._last_mtime = self._config_path.stat().st_mtime
        except FileNotFoundError:
            self._last_mtime = 0.0
        try:
            config = load_config(self._config_path)
            self._last_channels = config.channels.model_copy(deep=True)
            self._last_channels_hash = self._channels_hash(config.channels)
            self._last_show_tool_details = config.show_tool_details
            self._last_show_reasoning = config.show_reasoning
        except Exception:
            logger.exception("ConfigWatcher: failed to load initial config")
            self._last_channels = None
            self._last_channels_hash = None
            self._last_show_tool_details = None
            self._last_show_reasoning = None

    @staticmethod
    def _channels_hash(channels: ChannelConfig) -> int:
        """Fast hash of channels section for quick change detection."""
        return hash(json.dumps(channels.model_dump(mode="json"), sort_keys=True))

    async def _poll_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._poll_interval)
                await self._check()
            except Exception:
                logger.exception("ConfigWatcher: poll iteration failed")

    async def _check(self) -> None:
        # 1) Check mtime
        try:
            mtime = self._config_path.stat().st_mtime
        except FileNotFoundError:
            return
        if mtime == self._last_mtime:
            return
        self._last_mtime = mtime

        # 2) Load new config; quick-reject if channels section unchanged
        try:
            config = load_config(self._config_path)
        except Exception:
            logger.exception("ConfigWatcher: failed to parse config.json")
            return

        new_hash = self._channels_hash(config.channels)
        new_show_tool_details = config.show_tool_details
        new_show_reasoning = config.show_reasoning
        show_tool_details_changed = (
            self._last_show_tool_details is None
            or new_show_tool_details != self._last_show_tool_details
        )
        show_reasoning_changed = (
            self._last_show_reasoning is None
            or new_show_reasoning != self._last_show_reasoning
        )
        if (
            new_hash == self._last_channels_hash
            and not show_tool_details_changed
            and not show_reasoning_changed
        ):
            return  # Only non-channel fields changed (e.g. last_dispatch)

        # 3) Diff per channel instance and reload changed ones
        new_channels = config.channels
        old_channels = self._last_channels
        new_instances = get_channel_instances(new_channels)
        old_instances = (
            get_channel_instances(old_channels) if old_channels else {}
        )
        all_names = sorted(set(new_instances.keys()) | set(old_instances.keys()))

        for name in all_names:
            new_entry = new_instances.get(name)
            old_entry = old_instances.get(name)

            if new_entry is None and old_entry is not None:
                logger.info(
                    "ConfigWatcher: channel instance '%s' removed, stopping",
                    name,
                )
                try:
                    await self._channel_manager.remove_channel(name)
                except Exception:
                    logger.exception(
                        "ConfigWatcher: failed to remove channel '%s'",
                        name,
                    )
                continue

            if new_entry is None:
                continue

            new_type = str(new_entry.get("channel_type") or "").strip()
            new_ch = new_entry.get("config")
            old_type = str(old_entry.get("channel_type") or "").strip()
            old_ch = old_entry.get("config") if old_entry else None

            if isinstance(new_ch, dict):
                new_dump = new_ch
                old_dump = old_ch if isinstance(old_ch, dict) else None
            else:
                new_dump = (
                    new_ch.model_dump(mode="json")
                    if hasattr(new_ch, "model_dump")
                    else None
                )
                old_dump = (
                    old_ch.model_dump(mode="json")
                    if old_ch is not None and hasattr(old_ch, "model_dump")
                    else None
                )

            if (
                old_entry is not None
                and new_type == old_type
                and new_dump is not None
                and new_dump == old_dump
                and not show_tool_details_changed
                and not show_reasoning_changed
            ):
                continue

            logger.info(
                "ConfigWatcher: channel '%s' changed, reloading (type=%s)",
                name,
                new_type or "?",
            )
            try:
                new_channel = self._channel_manager.build_channel_from_config(
                    channels_cfg=new_channels,
                    instance_name=name,
                    channel_type=new_type,
                    raw_cfg=new_ch,
                    show_tool_details=new_show_tool_details,
                    show_reasoning=new_show_reasoning,
                )
                await self._channel_manager.replace_channel(new_channel)
                logger.info("ConfigWatcher: channel '%s' reloaded", name)
            except Exception:
                logger.exception(
                    "ConfigWatcher: failed to reload channel '%s'",
                    name,
                )

        # 4) Update snapshot
        self._last_channels = new_channels.model_copy(deep=True)
        self._last_channels_hash = self._channels_hash(new_channels)
        self._last_show_tool_details = new_show_tool_details
        self._last_show_reasoning = new_show_reasoning
