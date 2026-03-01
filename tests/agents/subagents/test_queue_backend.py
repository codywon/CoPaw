import asyncio

import pytest

from copaw.agents.subagents.queue import InProcQueue


@pytest.mark.asyncio
async def test_inproc_queue_enqueue_dequeue_and_size():
    queue = InProcQueue()
    await queue.enqueue("t1")
    await queue.enqueue("t2")
    assert queue.qsize() == 2

    assert await queue.dequeue() == "t1"
    assert await queue.dequeue() == "t2"
    assert queue.qsize() == 0


@pytest.mark.asyncio
async def test_inproc_queue_close_returns_none_on_empty_dequeue():
    queue = InProcQueue()
    queue.close()

    item = await asyncio.wait_for(queue.dequeue(), timeout=0.2)
    assert item is None


@pytest.mark.asyncio
async def test_inproc_queue_rejects_enqueue_after_close():
    queue = InProcQueue()
    queue.close()

    with pytest.raises(RuntimeError):
        await queue.enqueue("t1")
