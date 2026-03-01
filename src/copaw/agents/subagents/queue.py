# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from typing import Optional


_CLOSE_SENTINEL = "__subagent_queue_closed__"


class InProcQueue:
    """In-process queue backend for subagent task IDs."""

    def __init__(self, *, maxsize: int = 0) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=maxsize)
        self._closed = False

    async def enqueue(self, task_id: str) -> None:
        if self._closed:
            raise RuntimeError("Queue is closed")
        await self._queue.put(task_id)

    async def dequeue(self) -> Optional[str]:
        if self._closed and self._queue.empty():
            return None
        item = await self._queue.get()
        if item == _CLOSE_SENTINEL:
            return None
        return item

    def qsize(self) -> int:
        size = self._queue.qsize()
        if self._closed and size > 0:
            return max(0, size - 1)
        return size

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._queue.put_nowait(_CLOSE_SENTINEL)
        except asyncio.QueueFull:
            pass
