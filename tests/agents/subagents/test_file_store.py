import json

from copaw.agents.subagents.store import FileTaskStore


def test_file_store_persists_and_recovers_tasks(tmp_path):
    store_dir = tmp_path / "subagent_tasks"
    store = FileTaskStore(store_dir)
    task_id = store.create_task(
        parent_session_id="s1",
        task_prompt="persist me",
        selected_model_provider="openai",
        selected_model_name="gpt-5-chat",
    )
    store.set_status(task_id, "running")
    store.append_event(
        task_id,
        event_type="model_selected",
        summary="selected model",
        payload={"provider": "openai", "model": "gpt-5-chat"},
    )
    store.set_status(task_id, "success", result_summary="done")

    recovered = FileTaskStore(store_dir)
    task = recovered.get_task(task_id)
    assert task is not None
    assert task.status == "success"
    assert task.result_summary == "done"

    events = recovered.list_task_events(task_id)
    assert any(event.type == "model_selected" for event in events)
    assert any(
        event.status == "success"
        for event in events
        if event.type == "status_change"
    )


def test_file_store_writes_one_json_file_per_task(tmp_path):
    store_dir = tmp_path / "subagent_tasks"
    store = FileTaskStore(store_dir)
    task_id = store.create_task(parent_session_id="s1", task_prompt="json")
    store.set_status(task_id, "success", result_summary="ok")

    task_file = store_dir / f"{task_id}.json"
    assert task_file.exists()

    payload = json.loads(task_file.read_text(encoding="utf-8"))
    assert payload["task"]["task_id"] == task_id
    assert isinstance(payload["events"], list)
