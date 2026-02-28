# -*- coding: utf-8 -*-
from __future__ import annotations

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


def make_spawn_worker_tool(spawn_impl):
    """Create a tool function wrapper around an async spawn implementation."""

    async def spawn_worker(
        task: str,
        label: str = "",
        timeout_seconds: int | None = None,
        profile: str = "",
    ) -> ToolResponse:
        """Spawn a subagent worker to execute a delegated task.

        Args:
            task: The delegated task prompt for the subagent.
            label: Optional label to describe the task.
            timeout_seconds: Optional timeout override in seconds.
            profile: Optional worker profile name (reserved).
        """
        _ = profile  # Reserved for future worker profile selection
        result_text = await spawn_impl(
            task=task,
            label=label,
            timeout_seconds=timeout_seconds,
            profile=profile,
        )
        return ToolResponse(
            content=[
                TextBlock(
                    type="text",
                    text=result_text,
                ),
            ],
        )

    # Keep a stable tool name exposed to the model.
    spawn_worker.__name__ = "spawn_worker"
    return spawn_worker
