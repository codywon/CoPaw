# Enterprise Agent Platform MVP Spec (No Redis/PG)

Date: 2026-03-01  
Status: Approved for implementation

## 1. Objective
Build a production-usable multi-agent MVP for enterprise scenarios with:
- Main-agent orchestration of subagents
- Role-based specialization and routing
- Role-level model policy (quality/cost control)
- Task monitoring and basic auditability
- Clear extension seams for Redis/PostgreSQL in Phase 2

Constraint for this phase:
- Do not introduce Redis/pgvector/PostgreSQL
- Keep implementation lightweight, stable, and easy to migrate

## 2. MVP Scope
### In scope
- Subagent orchestration with configurable execution mode:
  - `sync` as default
  - `async` optional
- Role profiles:
  - `role_key`, `name`, `description`
  - `identity_prompt`, `tool_guidelines`, `routing_keywords`
  - `tool_allowlist`, `timeout_seconds`, `enabled`
- Role-level model policy:
  - `primary_model`
  - `fallback_models`
  - `max_tokens`
  - `budget_limit_usd` (soft limit for now)
  - `reasoning_effort` (if provider supports)
- Task state model and task monitor:
  - `queued`, `running`, `success`, `error`, `timeout`, `cancelled`
- Basic audit log:
  - task lifecycle
  - selected role/model
  - tool execution summary (respect `show_tool_details`)

### Out of scope (Phase 2)
- Redis queue and cache
- PostgreSQL + pgvector long-term memory
- Full ABAC and enterprise SSO
- Real-time streaming observability stack (Prometheus/Loki/Jaeger)

## 3. Architecture (MVP)
### 3.1 Control plane
- Config Center (existing `config.json`):
  - subagents global settings
  - role profiles
  - role model policy
- Policy Engine:
  - route by keyword + role enablement
  - enforce allowlists/timeouts

### 3.2 Execution plane
- Main Agent Orchestrator:
  - split tasks
  - choose role and model
  - dispatch to subagent worker
- In-process Worker Pool:
  - bounded concurrency (`max_concurrency`)
  - timeout and retry handling
- In-process Queue Backend:
  - `asyncio.Queue`

### 3.3 Data plane (temporary)
- `FileTaskStore` (JSON repository)
- `LocalAuditStore` (JSONL or structured log files)
- Existing session/memory files continue to work

## 4. Extension-first Interfaces
Implement with abstract interfaces first, then concrete local backends.

### 4.1 Queue backend
```python
class QueueBackend(Protocol):
    async def enqueue(self, task: SubagentTask) -> None: ...
    async def dequeue(self) -> SubagentTask | None: ...
    async def ack(self, task_id: str) -> None: ...
    async def retry(self, task_id: str, reason: str) -> None: ...
```

### 4.2 Task store
```python
class TaskStore(Protocol):
    def create(self, task: SubagentTask) -> None: ...
    def get(self, task_id: str) -> SubagentTask | None: ...
    def list(self, *, status: str | None, limit: int, offset: int) -> tuple[list[SubagentTask], int]: ...
    def update_status(self, task_id: str, status: str, **fields) -> None: ...
    def append_event(self, task_id: str, event: dict) -> None: ...
```

### 4.3 Model router
```python
class ModelRouter(Protocol):
    def select(self, role: SubagentRoleConfig, task_ctx: dict) -> ModelPlan: ...
```

ModelPlan minimal fields:
- `provider`
- `model`
- `fallback_chain`
- `max_tokens`
- `budget_limit_usd`

## 5. Data Model Additions
Add to `SubagentRoleConfig`:
- `model_provider: str = ""`
- `model_name: str = ""`  # primary
- `fallback_models: list[str] = []`
- `max_tokens: int | None = None`
- `budget_limit_usd: float | None = None`
- `reasoning_effort: str = ""`

Add to task record:
- `selected_role: str`
- `selected_model: str`
- `model_fallback_used: bool`
- `cost_estimate_usd: float | None`
- `events: list[TaskEvent]`

TaskEvent minimal fields:
- `ts`
- `type` (`dispatch`, `model_selected`, `tool_call`, `tool_result`, `status_change`, `error`)
- `summary`

## 6. API Contract (MVP)
Keep existing Subagents API and extend minimally.

### Existing/retained
- `GET /subagents/config`
- `PUT /subagents/config`
- `GET /subagents/tasks`
- `GET /subagents/tasks/{task_id}`
- `POST /subagents/tasks/{task_id}/cancel`

### New (MVP)
- `GET /subagents/tasks/{task_id}/events`
- `GET /subagents/roles/model-options`
  - return available providers/models from current provider registry

## 7. Frontend MVP (Web)
### 7.1 Subagents > Roles tab
Add a "Model Policy" section per role:
- provider
- primary model
- fallback models (multi-select)
- max tokens
- budget limit
- reasoning effort

### 7.2 Subagents > Tasks tab
- Keep polling-based monitor
- Add columns:
  - selected role
  - selected model
  - fallback used
  - cost estimate
- Task detail drawer:
  - event timeline
  - tool summary (detail visibility follows `show_tool_details`)

### 7.3 Channels
- Keep `show_tool_details` toggle (default ON)

## 8. Execution Strategy
### Step 1: Backend domain and storage abstraction
- Add interfaces and local implementations (`InProcQueue`, `FileTaskStore`)
- Migrate orchestrator calls to interfaces, not concrete file logic

### Step 2: Role-level model policy
- Extend config schema and validation
- Implement `ModelRouter.select(...)`
- Add fallback and timeout handling in dispatch path

### Step 3: Task events and audit
- Persist lifecycle events
- Expose events API

### Step 4: Frontend model policy + monitor enhancements
- Add role model policy form controls
- Add task columns and event timeline

## 9. Acceptance Criteria (MVP)
- Main agent can auto-dispatch to subagent based on role policy
- Role-level model policy is configurable in Web and takes effect at runtime
- System records task lifecycle and model selection for every dispatched task
- Task monitor displays live status and detail timeline via polling
- No Redis/PG dependency is required to run or test the full MVP
- Core modules are behind interfaces, allowing Phase 2 backend swap

## 10. Phase 2 Migration Plan (Preview)
Without changing upper business logic:
- `InProcQueue` -> `RedisQueue`
- `FileTaskStore` -> `PgTaskStore`
- `LocalMemoryStore` -> `PgVectorMemoryStore`
- add tenant-level budget and policy enforcement

Migration rule:
- Keep API and domain models backward compatible
- Migrate data with one-way idempotent scripts
