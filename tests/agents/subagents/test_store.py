from copaw.agents.subagents.store import InMemorySubagentTaskStore


def test_store_tracks_lifecycle():
    store = InMemorySubagentTaskStore()
    task_id = store.create_task(
        parent_session_id="s1",
        task_prompt="hello",
        role_key="research",
        dispatch_reason="force_when_matched:keyword",
        selected_model_provider="openai",
        selected_model_name="gpt-5-chat",
    )
    store.set_status(task_id, "running")
    store.set_status(task_id, "success", result_summary="done")

    task = store.get_task(task_id)
    assert task is not None
    assert task.status == "success"
    assert task.role_key == "research"
    assert task.dispatch_reason == "force_when_matched:keyword"
    assert task.selected_model_provider == "openai"
    assert task.selected_model_name == "gpt-5-chat"
    assert task.model_fallback_used is False
    assert task.result_summary == "done"
    assert task.duration_ms is not None


def test_cancel_terminal_task_keeps_terminal_status():
    store = InMemorySubagentTaskStore()
    task_id = store.create_task(parent_session_id="s1", task_prompt="hello")
    store.set_status(task_id, "error", error_message="failed")
    cancelled = store.cancel_task(task_id)

    assert cancelled is not None
    assert cancelled.status == "error"


def test_store_tracks_parent_child_relationship():
    store = InMemorySubagentTaskStore()
    parent_id = store.create_task(parent_session_id="s1", task_prompt="parent")
    child_1 = store.create_task(
        parent_session_id="s1",
        parent_task_id=parent_id,
        task_prompt="child-1",
    )
    child_2 = store.create_task(
        parent_session_id="s1",
        parent_task_id=child_1,
        task_prompt="child-2",
    )

    descendants = store.get_descendant_task_ids(parent_id)
    assert child_1 in descendants
    assert child_2 in descendants


def test_store_tracks_task_events():
    store = InMemorySubagentTaskStore()
    task_id = store.create_task(parent_session_id="s1", task_prompt="event task")

    events = store.list_task_events(task_id)
    assert len(events) == 1
    assert events[0].type == "status_change"
    assert events[0].status == "queued"

    store.set_status(task_id, "running")
    store.append_event(
        task_id,
        event_type="model_selected",
        summary="Selected openai/gpt-5-chat",
        payload={"provider": "openai", "model": "gpt-5-chat"},
    )
    store.set_status(task_id, "success", result_summary="ok")

    events = store.list_task_events(task_id)
    assert len(events) >= 4
    assert any(event.type == "model_selected" for event in events)
    assert any(event.status == "running" for event in events if event.type == "status_change")
    assert any(event.status == "success" for event in events if event.type == "status_change")
