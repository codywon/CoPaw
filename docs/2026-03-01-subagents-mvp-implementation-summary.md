# 2026-03-01 Subagents MVP Implementation Summary

## Scope Completed
This round implements the approved MVP upgrades for subagents, with focus on:
- role-level model policy
- subagent task model metadata
- task event timeline/audit API
- web console configuration + monitoring updates
- preserving existing sync-default orchestration behavior

## Backend Changes

### 1) Role model policy fields
Updated `SubagentRoleConfig` with:
- `model_provider`
- `model_name`
- `fallback_models`
- `max_tokens`
- `budget_limit_usd`
- `reasoning_effort`

Validation/normalization was extended in subagents router:
- trim and normalize provider/model/reasoning fields
- deduplicate fallback models
- remove fallback model equal to primary model

### 2) Task metadata and events
Extended subagent task domain model with:
- `selected_model_provider`
- `selected_model_name`
- `reasoning_effort`
- `model_fallback_used`
- `cost_estimate_usd`

Added task event model and response:
- `SubagentTaskEvent`
- `SubagentTaskEventListResponse`

Store behavior updates:
- task creation now records initial `queued` status event
- lifecycle status transitions append `status_change` events
- timeout/error branches append error events
- explicit APIs to append/list events

### 3) New APIs
Added endpoints:
- `GET /agent/subagents/tasks/{task_id}/events`
- `GET /agent/subagents/roles/model-options`

Model options endpoint returns provider/model options plus active provider/model context.

### 4) Main-agent dispatch integration
Main agent now resolves subagent model plan per role:
- prefer role-defined provider + primary model
- try fallback chain when needed
- fallback to active global model if role policy unresolved

Resolved plan metadata is persisted to subagent task records.
Subagent worker can be instantiated with per-role `llm_cfg` override.

### 5) Provider resolution utility
Added utility:
- `resolve_llm_config(provider_id, model, data=None)`

Used to resolve role-selected model runtime config without mutating active global model slot.

## Frontend Changes (Subagents)

### 1) Roles tab
Added per-role Model Policy controls:
- provider
- primary model
- fallback models
- max tokens
- budget limit (USD)
- reasoning effort

Provider/model options are loaded from backend `roles/model-options` endpoint.

### 2) Tasks tab
Added task list columns:
- selected model
- fallback used
- cost estimate

### 3) Task detail drawer
Added:
- selected model summary
- fallback used
- cost estimate
- task event timeline
- event payload inspection

### 4) i18n
Added EN/ZH keys for new labels and values in subagents page.

## Verification

### Backend tests
Executed:
- `pytest tests/config/test_subagents_config_schema.py tests/agents/subagents/test_policy.py tests/agents/subagents/test_store.py tests/agents/subagents/test_manager.py tests/app/routers/test_subagents_router.py`

Result:
- 25 passed

### Frontend build
Executed:
- `npm --prefix console run build`

Result:
- build success

## Notes
- Existing behavior remains: `sync` default, `async` optional, global concurrency and timeout controls unchanged.
- This phase keeps local/in-process architecture (no Redis/PG).
- Design remains extension-ready for phase 2 backend swaps.
