from fastapi import FastAPI
from fastapi.testclient import TestClient

from copaw.agents.subagents.store import InMemorySubagentTaskStore
from copaw.app.routers import subagents as subagents_router
from copaw.config.config import Config
from copaw.providers.models import ModelInfo, ModelSlotConfig, ProviderDefinition, ProvidersData


def _build_test_client(monkeypatch) -> TestClient:
    store = InMemorySubagentTaskStore()
    conf_holder = {"config": Config()}

    def _load_config():
        return conf_holder["config"]

    def _save_config(config):
        conf_holder["config"] = config

    monkeypatch.setattr(subagents_router, "load_config", _load_config)
    monkeypatch.setattr(subagents_router, "save_config", _save_config)
    monkeypatch.setattr(
        subagents_router,
        "get_subagent_task_store",
        lambda: store,
    )

    app = FastAPI()
    app.include_router(subagents_router.router, prefix="/api")
    return TestClient(app)


def test_get_and_put_subagents_config(monkeypatch):
    client = _build_test_client(monkeypatch)

    get_resp = client.get("/api/agent/subagents/config")
    assert get_resp.status_code == 200
    assert get_resp.json()["max_concurrency"] == 5

    payload = get_resp.json()
    payload["max_concurrency"] = 8
    payload["default_timeout_seconds"] = 60
    payload["hard_timeout_seconds"] = 120
    put_resp = client.put("/api/agent/subagents/config", json=payload)
    assert put_resp.status_code == 200
    assert put_resp.json()["max_concurrency"] == 8


def test_put_subagents_config_rejects_invalid_timeout(monkeypatch):
    client = _build_test_client(monkeypatch)
    payload = client.get("/api/agent/subagents/config").json()
    payload["default_timeout_seconds"] = 120
    payload["hard_timeout_seconds"] = 60

    resp = client.put("/api/agent/subagents/config", json=payload)
    assert resp.status_code == 400


def test_list_and_cancel_task(monkeypatch):
    client = _build_test_client(monkeypatch)

    store = subagents_router.get_subagent_task_store()
    task_id = store.create_task(parent_session_id="s1", task_prompt="test")
    store.set_status(task_id, "running")

    list_resp = client.get("/api/agent/subagents/tasks")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1

    cancel_resp = client.post(f"/api/agent/subagents/tasks/{task_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"


def test_cancel_task_cascades_to_descendants(monkeypatch):
    client = _build_test_client(monkeypatch)

    store = subagents_router.get_subagent_task_store()
    parent = store.create_task(parent_session_id="s1", task_prompt="parent")
    child = store.create_task(
        parent_session_id="s1",
        parent_task_id=parent,
        task_prompt="child",
    )
    store.set_status(parent, "running")
    store.set_status(child, "running")

    cancel_resp = client.post(f"/api/agent/subagents/tasks/{parent}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    child_snapshot = store.get_task(child)
    assert child_snapshot is not None
    assert child_snapshot.status == "cancelled"


def test_put_subagents_config_rejects_duplicate_role_keys(monkeypatch):
    client = _build_test_client(monkeypatch)
    payload = client.get("/api/agent/subagents/config").json()
    payload["roles"] = [
        {"key": "research", "name": "Research"},
        {"key": "research", "name": "Research2"},
    ]

    resp = client.put("/api/agent/subagents/config", json=payload)
    assert resp.status_code == 400


def test_put_subagents_config_rejects_unknown_default_role(monkeypatch):
    client = _build_test_client(monkeypatch)
    payload = client.get("/api/agent/subagents/config").json()
    payload["roles"] = [{"key": "research", "name": "Research"}]
    payload["default_role"] = "unknown"

    resp = client.put("/api/agent/subagents/config", json=payload)
    assert resp.status_code == 400


def test_get_subagent_task_events(monkeypatch):
    client = _build_test_client(monkeypatch)

    store = subagents_router.get_subagent_task_store()
    task_id = store.create_task(parent_session_id="s1", task_prompt="test")
    store.set_status(task_id, "running")
    store.set_status(task_id, "success", result_summary="ok")

    resp = client.get(f"/api/agent/subagents/tasks/{task_id}/events")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["task_id"] == task_id
    assert len(payload["items"]) >= 3
    assert payload["items"][0]["type"] == "status_change"


def test_get_model_options(monkeypatch):
    client = _build_test_client(monkeypatch)

    providers = [
        ProviderDefinition(
            id="openai",
            name="OpenAI",
            models=[ModelInfo(id="gpt-5-chat", name="GPT-5 Chat")],
        ),
        ProviderDefinition(
            id="ollama",
            name="Ollama",
            is_local=True,
            models=[ModelInfo(id="qwen3:8b", name="qwen3:8b")],
        ),
    ]

    providers_data = ProvidersData(
        active_llm=ModelSlotConfig(provider_id="openai", model="gpt-5-chat"),
    )

    monkeypatch.setattr(subagents_router, "list_providers", lambda: providers)
    monkeypatch.setattr(
        subagents_router,
        "load_providers_json",
        lambda: providers_data,
    )

    resp = client.get("/api/agent/subagents/roles/model-options")
    assert resp.status_code == 200
    body = resp.json()
    assert body["active_provider_id"] == "openai"
    assert body["active_model"] == "gpt-5-chat"
    assert len(body["providers"]) == 2
    assert body["providers"][0]["id"] == "openai"
    assert body["providers"][0]["models"][0]["id"] == "gpt-5-chat"
