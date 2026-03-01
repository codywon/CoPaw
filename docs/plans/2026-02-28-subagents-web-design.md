# Subagents Web Console Design

## 1. Context
CoPaw already has an `Agent` section in the web console with `Workspace`, `Skills`, `MCP`, and `Configuration`.  
The new requirement is to add a `Subagents` page under the same `Agent` menu and make it production-usable by combining:

1. Runtime configuration for subagent orchestration.
2. Task monitoring for running and completed subagent jobs.

This design assumes the current date baseline is February 28, 2026.

## 2. Confirmed Decisions

1. Navigation placement: under `Agent` main menu, same level as existing Agent pages.
2. Menu label: `Subagents`.
3. Page scope: one page with both `Config` and `Tasks` capabilities.
4. Information architecture: single route `/subagents` with two tabs:
   - `Config`
   - `Tasks`
5. UI constraint: visual style must stay consistent with current CoPaw console UI/UX.
6. I18n constraint: all new labels/messages/tooltips must support both Chinese and English switching.

## 3. Goals

1. Enable operators to configure subagent behavior without editing raw config files.
2. Provide near real-time visibility into subagent task lifecycle.
3. Allow cancellation of queued/running tasks from the web UI.
4. Keep behavior aligned with the multi-agent orchestration design already documented in this repository.

## 4. Non-Goals

1. No redesign of existing `Skills`, `MCP`, or `Configuration` pages.
2. No cross-instance distributed scheduler in this phase.
3. No automatic merge conflict resolver UI in this phase.
4. No replacement of existing agent runtime loop in this phase.

## 5. UX and Information Architecture

## 5.1 Sidebar and Routing

1. Add `Subagents` item in `console/src/layouts/Sidebar.tsx` under `agent-group`.
2. Add route `/subagents` in `console/src/layouts/MainLayout/index.tsx`.
3. Add path-key mapping for selection state so sidebar highlights correctly.

## 5.2 Page Layout

1. Header:
   - Title: `Subagents`
   - Description: runtime orchestration settings and task monitoring.
2. Body:
   - `Tabs` with `Config` and `Tasks`.
3. Shared states:
   - loading skeleton/state
   - inline error + retry
   - optimistic success message on save/cancel where applicable

## 5.5 Visual Consistency Rules

1. Reuse existing layout patterns used by `Agent/Config`, `MCP`, and `Workspace` pages.
2. Reuse existing component library (`@agentscope-ai/design` + current Ant Design wrappers), spacing rhythm, and card/form/table patterns.
3. Do not introduce a new visual language, custom theme, or inconsistent interaction pattern for this page.
4. Keep responsive behavior consistent with existing console pages on desktop and mobile widths.

## 5.6 Internationalization Rules

1. Add all new text keys in both `console/src/locales/en.json` and `console/src/locales/zh.json`.
2. No hardcoded display text in page components.
3. Error/success/loading/empty-state text must also go through i18n keys.
4. Language switch should update all `Subagents` page content immediately, consistent with current app behavior.

## 5.3 Config Tab

Editable fields:

1. `enabled` (boolean)
2. `max_concurrency` (int, default 5)
3. `default_timeout_seconds` (int)
4. `hard_timeout_seconds` (int)
5. `write_mode` (`worktree` or `direct`)
6. `allow_nested_spawn` (boolean, default false)
7. `allowed_paths` (list of absolute paths)
8. `tools.default_enabled` (list of tool ids; default includes `web_search`, `web_fetch`)
9. `mcp_policy` (`none`, `selected`, `all`)
10. `mcp_selected` (list, active only when policy is `selected`)
11. `skills_policy` (`none`, `selected`, `all`)
12. `skills_selected` (list, active only when policy is `selected`)

Validation rules:

1. `max_concurrency >= 1`
2. `default_timeout_seconds >= 1`
3. `hard_timeout_seconds >= default_timeout_seconds`
4. `allowed_paths` entries normalized and deduplicated
5. `selected` policy requires non-empty selection list

## 5.4 Tasks Tab

Primary capabilities:

1. List tasks with status filters.
2. Show key fields: task id, label, status, start/end time, duration, summary.
3. Open details pane/drawer for full task context and artifacts.
4. Cancel queued/running tasks.
5. Poll list every 3 seconds while tab is active; support manual refresh.

Status set:

1. `queued`
2. `running`
3. `success`
4. `error`
5. `timeout`
6. `cancelled`

## 6. Backend API Contract

Prefix: `/api/agent/subagents`

## 6.1 Config Endpoints

1. `GET /config`
   - Returns full subagents config object.
2. `PUT /config`
   - Replaces full subagents config object after validation.
   - Returns saved object.

## 6.2 Task Endpoints

1. `GET /tasks?status=&limit=&offset=`
   - Returns paginated list response.
2. `GET /tasks/{task_id}`
   - Returns task detail.
3. `POST /tasks/{task_id}/cancel`
   - Cancels if status is `queued` or `running`.
   - Returns updated task.

## 6.3 Error Contract

1. `400` for validation errors.
2. `404` for unknown task id.
3. `409` for invalid state transitions (for example cancel after completion).
4. `500` for unexpected runtime errors.

## 7. Security and Guardrails

1. `worktree` remains the default write mode.
2. Switching to `direct` shows explicit risk warning in UI.
3. Path guard applies server-side regardless of UI constraints.
4. `allow_nested_spawn` defaults to false and is clearly marked advanced.
5. `mcp_policy=all` and `skills_policy=all` show elevated-risk warning text.

## 8. Data Flow

1. User opens `/subagents`.
2. Frontend fetches config and task list in parallel for first paint.
3. `Config` save triggers `PUT /config`, then re-fetch for canonical server state.
4. `Tasks` tab starts polling loop; each cycle updates list state.
5. User opens task detail -> `GET /tasks/{task_id}`.
6. User clicks cancel -> `POST /tasks/{task_id}/cancel` -> list row updates.

## 9. Failure Handling and UX Degradation

1. Config load failure:
   - show blocking error state with retry.
2. Config save failure:
   - keep form values, show inline error toast, do not clear dirty state.
3. Task list load/poll failure:
   - keep last successful snapshot and mark stale state.
4. Task detail failure:
   - show local detail panel error only; keep list usable.
5. Cancel failure:
   - show row-level/notification error with reason.

## 10. Testing Strategy

Backend:

1. Schema tests for config defaults and validation.
2. Router tests for `config/tasks/detail/cancel`.
3. State transition tests for task cancellation and timeout handling.

Frontend:

1. API client type-contract checks.
2. Route/menu integration checks via build and lint gates.
3. Manual functional verification for tab switching, save/reset, polling, detail, cancel.
4. Manual i18n verification: all `Subagents` texts render correctly in both Chinese and English.
5. Manual UI consistency verification against existing `Agent` pages (layout, spacing, controls, interaction feedback).

## 11. Acceptance Criteria

1. Sidebar shows `Agent > Subagents` and route works.
2. Config tab can load, edit, validate, save, and reset.
3. Tasks tab can list, filter, refresh, poll, open details, and cancel eligible tasks.
4. Invalid config values are blocked by both frontend and backend.
5. Existing pages (`Workspace`, `Skills`, `MCP`, `Configuration`) are unaffected.
6. `Subagents` page style is visually consistent with existing console UI/UX.
7. `Subagents` page fully supports Chinese and English language switching.

## 12. Rollout Plan

1. Ship backend API and config schema first.
2. Ship frontend page behind regular navigation in same release.
3. Observe logs for task endpoint errors and config validation failures.
4. Iterate on task detail richness after first operator feedback cycle.
