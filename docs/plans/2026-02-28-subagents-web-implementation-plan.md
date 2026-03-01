# Subagents Web Console Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a production-usable `Agent > Subagents` web page that supports both subagent runtime configuration and task monitoring.

**Architecture:** Extend backend config and task APIs under `/api/agent/subagents`, then add a new frontend page at `/subagents` with two tabs (`Config` and `Tasks`). The backend exposes validated config and task lifecycle endpoints; the frontend consumes those endpoints with typed API clients and shows real-time task state via polling. The page must follow existing console UI/UX patterns and provide complete Chinese/English i18n coverage.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, asyncio, React 18, TypeScript, Ant Design, i18next

---

## Execution Rules

- @superpowers:test-driven-development
- @superpowers:systematic-debugging
- @superpowers:verification-before-completion
- Prefer one focused commit per task.
- Keep changes DRY and YAGNI.

### Task 1: Add subagents config schema in backend config model

**Files:**
- Modify: `src/copaw/config/config.py`
- Test: `tests/config/test_subagents_config_schema.py`

**Step 1: Write the failing test**

```python
from copaw.config.config import AgentsConfig

def test_subagents_defaults_loaded():
    cfg = AgentsConfig()
    assert cfg.subagents.max_concurrency == 5
    assert cfg.subagents.write_mode == "worktree"
    assert "web_search" in cfg.subagents.tools.default_enabled
    assert "web_fetch" in cfg.subagents.tools.default_enabled
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/config/test_subagents_config_schema.py::test_subagents_defaults_loaded -v`  
Expected: FAIL with missing `subagents` in `AgentsConfig`.

**Step 3: Write minimal implementation**

- Add `SubagentToolsConfig` and `SubagentsConfig` models.
- Add `subagents: SubagentsConfig` field to `AgentsConfig`.
- Keep defaults aligned with design (`max_concurrency=5`, `write_mode="worktree"`, web tools enabled).

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/config/test_subagents_config_schema.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/copaw/config/config.py tests/config/test_subagents_config_schema.py
git commit -m "feat(config): add subagents runtime config schema and defaults"
```

### Task 2: Add in-memory subagent task models and store

**Files:**
- Create: `src/copaw/agents/subagents/models.py`
- Create: `src/copaw/agents/subagents/store.py`
- Create: `src/copaw/agents/subagents/__init__.py`
- Test: `tests/agents/subagents/test_store.py`

**Step 1: Write the failing test**

```python
from copaw.agents.subagents.store import InMemorySubagentTaskStore

def test_store_tracks_lifecycle():
    store = InMemorySubagentTaskStore()
    tid = store.create_task(parent_session_id="s1", task_prompt="hello")
    store.mark_running(tid)
    store.mark_success(tid, result_summary="done")
    task = store.get_task(tid)
    assert task.status == "success"
    assert task.result_summary == "done"
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/agents/subagents/test_store.py::test_store_tracks_lifecycle -v`  
Expected: FAIL with module not found.

**Step 3: Write minimal implementation**

- Define task status enum/literals (`queued`, `running`, `success`, `error`, `timeout`, `cancelled`).
- Implement a simple thread-safe in-memory store with create/list/get/update/cancel primitives.

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/agents/subagents/test_store.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/copaw/agents/subagents/models.py src/copaw/agents/subagents/store.py src/copaw/agents/subagents/__init__.py tests/agents/subagents/test_store.py
git commit -m "feat(subagents): add task models and in-memory task store"
```

### Task 3: Add `/agent/subagents/config` API endpoints

**Files:**
- Create: `src/copaw/app/routers/subagents.py`
- Modify: `src/copaw/app/routers/__init__.py`
- Test: `tests/app/routers/test_subagents_config_router.py`

**Step 1: Write the failing test**

```python
def test_get_subagents_config(client):
    resp = client.get("/api/agent/subagents/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["max_concurrency"] == 5
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/app/routers/test_subagents_config_router.py::test_get_subagents_config -v`  
Expected: FAIL with route not found.

**Step 3: Write minimal implementation**

- Add `GET /agent/subagents/config` and `PUT /agent/subagents/config`.
- Read/write `config.agents.subagents` through existing `load_config/save_config`.
- Add validation guard for timeout relation and selected-policy lists.

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/app/routers/test_subagents_config_router.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/copaw/app/routers/subagents.py src/copaw/app/routers/__init__.py tests/app/routers/test_subagents_config_router.py
git commit -m "feat(api): add subagents config get and update endpoints"
```

### Task 4: Add `/agent/subagents/tasks` list/detail/cancel endpoints

**Files:**
- Modify: `src/copaw/app/routers/subagents.py`
- Modify: `src/copaw/agents/subagents/store.py`
- Test: `tests/app/routers/test_subagents_tasks_router.py`

**Step 1: Write the failing test**

```python
def test_list_subagent_tasks(client):
    resp = client.get("/api/agent/subagents/tasks")
    assert resp.status_code == 200
    assert "items" in resp.json()
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/app/routers/test_subagents_tasks_router.py::test_list_subagent_tasks -v`  
Expected: FAIL with route not found or shape mismatch.

**Step 3: Write minimal implementation**

- Add:
  - `GET /agent/subagents/tasks`
  - `GET /agent/subagents/tasks/{task_id}`
  - `POST /agent/subagents/tasks/{task_id}/cancel`
- Return `404` for unknown id and `409` for invalid cancel state.
- Keep API response shape stable for frontend table/detail usage.

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/app/routers/test_subagents_tasks_router.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/copaw/app/routers/subagents.py src/copaw/agents/subagents/store.py tests/app/routers/test_subagents_tasks_router.py
git commit -m "feat(api): add subagents tasks list detail and cancel endpoints"
```

### Task 5: Add typed frontend API contracts for subagents

**Files:**
- Create: `console/src/api/types/subagents.ts`
- Create: `console/src/api/modules/subagents.ts`
- Modify: `console/src/api/types/index.ts`
- Modify: `console/src/api/index.ts`
- Verify: `console/src/api/modules/agent.ts` (no change expected unless refactor needed)

**Step 1: Write the failing compile contract**

Create temporary compile-check file:

```ts
import api from "../index";
import type { SubagentsConfig } from "../types";

async function contractSmoke() {
  const cfg: SubagentsConfig = await api.getSubagentsConfig();
  await api.updateSubagentsConfig(cfg);
  await api.listSubagentTasks();
}

void contractSmoke;
```

**Step 2: Run build to verify it fails**

Run: `cd console; npm run build`  
Expected: FAIL because subagents types/methods do not exist yet.

**Step 3: Write minimal implementation**

- Add subagents config/task interfaces.
- Add API module methods:
  - `getSubagentsConfig`
  - `updateSubagentsConfig`
  - `listSubagentTasks`
  - `getSubagentTask`
  - `cancelSubagentTask`
- Export module through API aggregator.
- Remove temporary compile-check file after methods exist.

**Step 4: Run build to verify it passes**

Run: `cd console; npm run build`  
Expected: PASS.

**Step 5: Commit**

```bash
git add console/src/api/types/subagents.ts console/src/api/modules/subagents.ts console/src/api/types/index.ts console/src/api/index.ts
git commit -m "feat(console-api): add typed subagents config and tasks client"
```

### Task 6: Add route and sidebar navigation for `Subagents`

**Files:**
- Modify: `console/src/layouts/MainLayout/index.tsx`
- Modify: `console/src/layouts/Sidebar.tsx`
- Modify: `console/src/locales/en.json`
- Modify: `console/src/locales/zh.json`

**Step 1: Write the failing compile check**

- Add route import and menu key references before creating the page file.

**Step 2: Run build to verify it fails**

Run: `cd console; npm run build`  
Expected: FAIL with missing page import.

**Step 3: Write minimal implementation**

- Add `/subagents` in route switch.
- Add `subagents` key in path mappings.
- Add `Agent > Subagents` menu item.
- Add locale keys:
  - `nav.subagents`
  - `subagents.*` (page title/description/basic labels).
- Follow existing sidebar/menu visual patterns and interaction behavior (no custom style deviation).

**Step 4: Run build to verify it passes**

Run: `cd console; npm run build`  
Expected: PASS.

**Step 5: Commit**

```bash
git add console/src/layouts/MainLayout/index.tsx console/src/layouts/Sidebar.tsx console/src/locales/en.json console/src/locales/zh.json
git commit -m "feat(console): add subagents route sidebar nav and locale keys"
```

### Task 7: Implement `Subagents` page Config tab

**Files:**
- Create: `console/src/pages/Agent/Subagents/index.tsx`
- Create: `console/src/pages/Agent/Subagents/index.module.less`

**Step 1: Write a failing behavior check**

- Implement the page shell with `Config` tab only and call `api.getSubagentsConfig` before handlers exist.

**Step 2: Run build to verify it fails**

Run: `cd console; npm run build`  
Expected: FAIL on missing handlers/field mapping.

**Step 3: Write minimal implementation**

- Add load/save/reset flow for config form.
- Add frontend validation for all numeric and policy fields.
- Add conditional UI behavior for `selected` policy lists.
- Add warning UI when `write_mode` is `direct`.
- Reuse existing page/form/card visual styles from current `Agent` pages.
- Add all new UI strings in both `console/src/locales/en.json` and `console/src/locales/zh.json` (no hardcoded strings).

**Step 4: Run build and lint to verify it passes**

Run:
- `cd console; npm run lint`
- `cd console; npm run build`

Expected: PASS for both commands.

**Step 5: Commit**

```bash
git add console/src/pages/Agent/Subagents/index.tsx console/src/pages/Agent/Subagents/index.module.less
git commit -m "feat(console): add subagents config tab with validation and save flow"
```

### Task 8: Implement `Subagents` page Tasks tab with polling/detail/cancel

**Files:**
- Modify: `console/src/pages/Agent/Subagents/index.tsx`
- Modify: `console/src/pages/Agent/Subagents/index.module.less`
- Modify: `console/src/locales/en.json`
- Modify: `console/src/locales/zh.json`

**Step 1: Write a failing behavior check**

- Add task table skeleton wired to `listSubagentTasks` without parser/state mapping.

**Step 2: Run build to verify it fails**

Run: `cd console; npm run build`  
Expected: FAIL due to unresolved task state shape usage.

**Step 3: Write minimal implementation**

- Add status filter controls.
- Poll every 3 seconds while `Tasks` tab is active.
- Add row actions:
  - `View Details` -> detail drawer/panel using `getSubagentTask`.
  - `Cancel` for `queued`/`running` only using `cancelSubagentTask`.
- Keep last successful snapshot when a polling cycle fails.
- Keep table, filter, drawer, and feedback interactions aligned with existing console UX patterns.
- Add full bilingual text coverage for statuses/actions/errors/empty states/tooltips.

**Step 4: Run build and lint to verify it passes**

Run:
- `cd console; npm run lint`
- `cd console; npm run build`

Expected: PASS for both commands.

**Step 5: Commit**

```bash
git add console/src/pages/Agent/Subagents/index.tsx console/src/pages/Agent/Subagents/index.module.less console/src/locales/en.json console/src/locales/zh.json
git commit -m "feat(console): add subagents tasks monitoring with polling detail and cancel"
```

### Task 9: End-to-end verification and documentation updates

**Files:**
- Modify: `docs/2026-02-28-multi-agent-orchestration-design-report.md`
- Modify: `docs/plans/2026-02-28-main-agent-subagents-implementation-plan.md`
- (Optional) Create: `docs/ops/subagents-console-runbook.md`

**Step 1: Run backend tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/config tests/agents/subagents tests/app/routers -v`  
Expected: PASS (or only known unrelated failures documented).

**Step 2: Run frontend quality gates**

Run:
- `cd console; npm run lint`
- `cd console; npm run build`

Expected: PASS.

**Step 3: Manual smoke test**

1. Open `/subagents`.
2. Save config with valid data and confirm persistence.
3. Trigger at least one mock/real task and verify list updates.
4. Open detail and cancel a cancellable task.
5. Switch language to Chinese and English; verify all `Subagents` texts switch correctly.
6. Compare page visual behavior with existing `Agent` pages and confirm consistency.

Expected: all flows work; no console/runtime errors.

**Step 4: Update docs minimally**

- Add a short section linking the new UI entrypoint and API endpoints.
- Document polling cadence and cancel semantics.

**Step 5: Commit**

```bash
git add docs/2026-02-28-multi-agent-orchestration-design-report.md docs/plans/2026-02-28-main-agent-subagents-implementation-plan.md docs/ops/subagents-console-runbook.md
git commit -m "docs(subagents): add console config and task monitoring guidance"
```

## Acceptance Criteria

1. `Agent > Subagents` is visible and route `/subagents` works.
2. `Config` tab supports load, validate, save, and reset.
3. `Tasks` tab supports list, poll, detail, and cancel.
4. Backend validates unsafe/invalid config combinations.
5. Existing agent pages continue to behave as before.
6. New page UI/UX is consistent with the existing console style.
7. New page supports complete Chinese/English switching for all added text.

## Rollback Plan

1. Remove sidebar entry and route to hide UI quickly.
2. Keep backend endpoints but gate them behind `enabled=false` if needed.
3. Revert specific commits in reverse order if full rollback is required.
