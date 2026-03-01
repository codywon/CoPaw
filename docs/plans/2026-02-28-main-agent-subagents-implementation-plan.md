# Main-Agent Subagents Orchestration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 CoPaw 中实现“主代理统一调度多个可写从代理”的 PoC，支持并发、超时、路径白名单、MCP/Skill 可配置策略，并通过主代理统一向用户输出结果。  

**Architecture:** 保持现有 `CoPawAgent + AgentRunner` 主流程不变，新增 `SubagentManager`、`spawn_worker` 工具和子任务状态存储；从代理使用受限工具集和独立上下文执行，完成后通过 Runner 桥接回主会话，由主代理统一总结回复。默认 `worktree` 隔离写入，`direct` 作为显式可选策略。  

**Tech Stack:** Python 3.11, FastAPI, AgentScope/ReActAgent, asyncio, pytest

---

## Execution Rules

- @superpowers:test-driven-development
- @superpowers:systematic-debugging
- @superpowers:verification-before-completion
- 单任务单提交，避免混改。
- 默认先写测试再写实现（Red -> Green -> Refactor）。

### Task 1: Subagent 配置模型与加载

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
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/config/test_subagents_config_schema.py::test_subagents_defaults_loaded -v`  
Expected: FAIL with `AttributeError` or missing `subagents`.

**Step 3: Write minimal implementation**

- 在 `AgentsConfig` 增加 `subagents` 字段与相关 Pydantic 模型：
  - `SubagentsConfig`
  - `SubagentToolsConfig`
  - 策略枚举字段：`write_mode`, `mcp_policy`, `skills_policy`

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/config/test_subagents_config_schema.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/copaw/config/config.py tests/config/test_subagents_config_schema.py
git commit -m "feat(config): add subagent orchestration config schema"
```

### Task 2: 子任务数据模型与状态存储

**Files:**
- Create: `src/copaw/agents/subagents/models.py`
- Create: `src/copaw/agents/subagents/store.py`
- Test: `tests/agents/subagents/test_store.py`

**Step 1: Write the failing test**

```python
from copaw.agents.subagents.store import InMemorySubagentStore

def test_store_tracks_status_transitions():
    store = InMemorySubagentStore()
    tid = store.create_task(parent_session_id="s1", task_prompt="x")
    store.mark_running(tid)
    store.mark_success(tid, "done")
    task = store.get_task(tid)
    assert task.status == "success"
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/agents/subagents/test_store.py::test_store_tracks_status_transitions -v`  
Expected: FAIL with module not found.

**Step 3: Write minimal implementation**

- 定义 `SubagentTask`、`SubagentTaskStatus`、`SubagentResult`。
- 实现线程安全/协程安全的内存存储（`asyncio.Lock`）。

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/agents/subagents/test_store.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/copaw/agents/subagents/models.py src/copaw/agents/subagents/store.py tests/agents/subagents/test_store.py
git commit -m "feat(subagents): add task models and in-memory task store"
```

### Task 3: 路径白名单与写入模式守卫

**Files:**
- Create: `src/copaw/agents/subagents/path_guard.py`
- Test: `tests/agents/subagents/test_path_guard.py`

**Step 1: Write the failing test**

```python
from copaw.agents.subagents.path_guard import is_path_allowed

def test_denies_path_outside_whitelist(tmp_path):
    allowed = [tmp_path / "workspace"]
    blocked = tmp_path / "other" / "x.txt"
    assert not is_path_allowed(blocked, allowed)
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/agents/subagents/test_path_guard.py::test_denies_path_outside_whitelist -v`  
Expected: FAIL with module not found.

**Step 3: Write minimal implementation**

- 实现路径规范化（resolve）。
- 防止路径逃逸（`..`/符号链接）。
- 对 `worktree` 与 `direct` 模式统一复用校验逻辑。

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/agents/subagents/test_path_guard.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/copaw/agents/subagents/path_guard.py tests/agents/subagents/test_path_guard.py
git commit -m "feat(subagents): add allowed-path guard for direct/worktree modes"
```

### Task 4: SubagentManager（并发、超时、任务生命周期）

**Files:**
- Create: `src/copaw/agents/subagents/manager.py`
- Modify: `src/copaw/agents/subagents/__init__.py` (new export)
- Test: `tests/agents/subagents/test_manager.py`

**Step 1: Write the failing test**

```python
import asyncio
from copaw.agents.subagents.manager import SubagentManager

async def test_manager_enforces_max_concurrency():
    mgr = SubagentManager(max_concurrency=2, default_timeout_seconds=60)
    running = await mgr.debug_running_count()
    assert running == 0
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/agents/subagents/test_manager.py::test_manager_enforces_max_concurrency -v`  
Expected: FAIL with module not found / missing method.

**Step 3: Write minimal implementation**

- `spawn()` 入队并返回 `task_id`。
- `Semaphore` 控制并发。
- `asyncio.wait_for` 执行超时控制（默认与 hard timeout）。
- 状态写入 `store`（queued/running/success/error/timeout）。

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/agents/subagents/test_manager.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/copaw/agents/subagents/manager.py src/copaw/agents/subagents/__init__.py tests/agents/subagents/test_manager.py
git commit -m "feat(subagents): add manager with queue concurrency and timeout control"
```

### Task 5: spawn_worker 工具接入主代理

**Files:**
- Create: `src/copaw/agents/tools/spawn_worker.py`
- Modify: `src/copaw/agents/tools/__init__.py`
- Modify: `src/copaw/agents/react_agent.py`
- Test: `tests/agents/tools/test_spawn_worker_tool.py`
- Test: `tests/agents/test_react_agent_tool_registration.py`

**Step 1: Write the failing test**

```python
def test_spawn_worker_registered_for_main_agent():
    # construct main CoPawAgent
    # assert toolkit has spawn_worker
    ...
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/agents/test_react_agent_tool_registration.py::test_spawn_worker_registered_for_main_agent -v`  
Expected: FAIL because tool not registered.

**Step 3: Write minimal implementation**

- `spawn_worker` 参数：`task`, `label?`, `timeout_seconds?`, `profile?`。
- 在 `CoPawAgent._create_toolkit()` 中按角色注册：
  - 主代理：注册 `spawn_worker`
  - 从代理：不注册 `spawn_worker`

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/agents/tools/test_spawn_worker_tool.py tests/agents/test_react_agent_tool_registration.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/copaw/agents/tools/spawn_worker.py src/copaw/agents/tools/__init__.py src/copaw/agents/react_agent.py tests/agents/tools/test_spawn_worker_tool.py tests/agents/test_react_agent_tool_registration.py
git commit -m "feat(agent): add spawn_worker tool and role-based tool registration"
```

### Task 6: 从代理执行器与工具/MCP/Skill 策略

**Files:**
- Create: `src/copaw/agents/subagents/worker_factory.py`
- Modify: `src/copaw/agents/react_agent.py`
- Test: `tests/agents/subagents/test_worker_policy.py`

**Step 1: Write the failing test**

```python
def test_worker_respects_policy_selected_mcp_and_skills():
    # build worker config with selected mode
    # assert only selected clients/skills are visible
    ...
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/agents/subagents/test_worker_policy.py -v`  
Expected: FAIL with missing policy filter.

**Step 3: Write minimal implementation**

- Worker Factory 根据 `mcp_policy/skills_policy` 构建从代理可用集。
- 默认启用 `web_search/web_fetch`（若工具存在），并支持配置覆盖。
- 从代理禁用用户直发消息与嵌套 spawn。

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/agents/subagents/test_worker_policy.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/copaw/agents/subagents/worker_factory.py src/copaw/agents/react_agent.py tests/agents/subagents/test_worker_policy.py
git commit -m "feat(subagents): enforce tool MCP and skill policy for workers"
```

### Task 7: Runner 桥接回传（主代理统一对外回复）

**Files:**
- Modify: `src/copaw/app/runner/runner.py`
- Modify: `src/copaw/app/_app.py`
- Create: `src/copaw/app/subagents/bridge.py`
- Test: `tests/app/subagents/test_bridge.py`

**Step 1: Write the failing test**

```python
async def test_subagent_result_reinjected_to_parent_session():
    # submit fake result event
    # assert runner processes event in same session
    ...
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/app/subagents/test_bridge.py -v`  
Expected: FAIL due to missing bridge/reinject flow.

**Step 3: Write minimal implementation**

- `SubagentManager` 完成任务后向桥接器提交结果。
- 桥接器构造系统消息触发主代理在原会话中二次处理。
- 由主代理输出最终用户可读答复。

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/app/subagents/test_bridge.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/copaw/app/runner/runner.py src/copaw/app/_app.py src/copaw/app/subagents/bridge.py tests/app/subagents/test_bridge.py
git commit -m "feat(runner): bridge subagent results back to parent session through main agent"
```

### Task 8: Subagent 任务查询与取消 API（PoC 运维面）

**Files:**
- Create: `src/copaw/app/routers/subagents.py`
- Modify: `src/copaw/app/routers/__init__.py`
- Test: `tests/app/routers/test_subagents_router.py`

**Step 1: Write the failing test**

```python
def test_list_subagent_tasks_endpoint(client):
    resp = client.get("/api/subagents/tasks")
    assert resp.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/app/routers/test_subagents_router.py -v`  
Expected: FAIL with route not found.

**Step 3: Write minimal implementation**

- `GET /api/subagents/tasks`
- `GET /api/subagents/tasks/{task_id}`
- `POST /api/subagents/tasks/{task_id}/cancel`

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/app/routers/test_subagents_router.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add src/copaw/app/routers/subagents.py src/copaw/app/routers/__init__.py tests/app/routers/test_subagents_router.py
git commit -m "feat(api): add subagent task list detail and cancel endpoints"
```

### Task 9: 端到端集成验证（并发、超时、路径白名单）

**Files:**
- Create: `tests/integration/test_subagent_orchestration.py`

**Step 1: Write the failing test**

```python
def test_orchestration_happy_path(main_agent_client):
    # user asks main agent to spawn two workers
    # assert both complete and final answer is from main agent
    ...
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_subagent_orchestration.py -v`  
Expected: FAIL before full orchestration wiring is complete.

**Step 3: Write minimal implementation**

- 如仍有缺口，只补足与测试直接相关最小实现。
- 不做额外功能扩展。

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/integration/test_subagent_orchestration.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add tests/integration/test_subagent_orchestration.py
git commit -m "test(integration): verify main-agent subagent orchestration e2e"
```

### Task 10: 全量回归与文档更新

**Files:**
- Modify: `website/public/docs/config.en.md`
- Modify: `website/public/docs/config.zh.md`
- Modify: `website/public/docs/faq.en.md`
- Modify: `website/public/docs/faq.zh.md`

**Step 1: Write failing doc checks (if any lint exists)**

若项目有文档 lint，先新增检查；若无，记录“手动验证项”。

**Step 2: Run pre-check**

Run: `.\.venv\Scripts\python.exe -m pytest -q`  
Expected: Existing failures identified and triaged.

**Step 3: Update docs minimally**

- 新增 `agents.subagents` 配置说明。
- 补充“默认 worktree、direct 可选、路径白名单、并发与超时”说明。
- FAQ 增加“长任务超时与并发配置”条目。

**Step 4: Final verification**

Run:
- `.\.venv\Scripts\python.exe -m pytest -q`
- `.\.venv\Scripts\python.exe -m pip check`

Expected:
- 测试通过（或仅剩已知无关失败并记录）
- `pip check` 无新增依赖冲突

**Step 5: Commit**

```bash
git add website/public/docs/config.en.md website/public/docs/config.zh.md website/public/docs/faq.en.md website/public/docs/faq.zh.md
git commit -m "docs: add subagent orchestration config and operations guidance"
```

## Acceptance Criteria

1. 主代理可并发调度最多 `max_concurrency` 个从代理。
2. 从代理支持可写执行，且遵守 `write_mode + allowed_paths`。
3. 从代理结果由主代理统一对用户表达（非直接绕过）。
4. `MCP/Skill` 策略可配置，且策略生效有测试覆盖。
5. 可通过 API 查询任务状态并取消任务。
6. 默认配置满足：并发 5、web_search/fetch 开启、长任务可配置超时。

## Rollback Plan

1. 关闭 `agents.subagents.enabled=false` 即可回退到单代理模式。
2. 保留旧 Runner 路径，桥接器异常时不影响普通会话。
3. `write_mode` 强制回退到 `worktree` 可快速降低风险。

