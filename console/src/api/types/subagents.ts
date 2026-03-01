export type SubagentPolicy = "none" | "selected" | "all";
export type SubagentRolePolicy = "inherit" | "none" | "selected" | "all";
export type SubagentWriteMode = "worktree" | "direct";
export type SubagentExecutionMode = "sync" | "async";
export type SubagentDispatchMode =
  | "advisory"
  | "force_when_matched"
  | "force_by_default";
export type SubagentRoleSelectionMode = "auto" | "default";
export type SubagentTaskStatus =
  | "queued"
  | "running"
  | "success"
  | "error"
  | "timeout"
  | "cancelled";
export type SubagentTaskEventType =
  | "dispatch"
  | "model_selected"
  | "tool_call"
  | "tool_result"
  | "status_change"
  | "error";

export interface SubagentToolsConfig {
  default_enabled: string[];
}

export interface SubagentRoleConfig {
  key: string;
  name: string;
  description: string;
  identity_prompt: string;
  tool_guidelines: string;
  enabled: boolean;
  routing_keywords: string[];
  tool_allowlist: string[];
  timeout_seconds?: number | null;
  model_provider: string;
  model_name: string;
  fallback_models: string[];
  max_tokens?: number | null;
  budget_limit_usd?: number | null;
  reasoning_effort: string;
  mcp_policy: SubagentRolePolicy;
  mcp_selected: string[];
  skills_policy: SubagentRolePolicy;
  skills_selected: string[];
}

export interface SubagentsConfig {
  enabled: boolean;
  max_concurrency: number;
  default_timeout_seconds: number;
  hard_timeout_seconds: number;
  execution_mode: SubagentExecutionMode;
  retry_max_attempts: number;
  retry_backoff_seconds: number;
  write_mode: SubagentWriteMode;
  allow_nested_spawn: boolean;
  dispatch_mode: SubagentDispatchMode;
  auto_dispatch_keywords: string[];
  auto_dispatch_min_prompt_chars: number;
  role_selection_mode: SubagentRoleSelectionMode;
  default_role: string;
  roles: SubagentRoleConfig[];
  allowed_paths: string[];
  tools: SubagentToolsConfig;
  mcp_policy: SubagentPolicy;
  mcp_selected: string[];
  skills_policy: SubagentPolicy;
  skills_selected: string[];
}

export interface SubagentTask {
  task_id: string;
  status: SubagentTaskStatus;
  parent_session_id: string;
  origin_user_id: string;
  origin_channel: string;
  label: string;
  role_key: string;
  dispatch_reason: string;
  task_prompt: string;
  write_mode: string;
  allowed_paths: string[];
  selected_model_provider: string;
  selected_model_name: string;
  reasoning_effort: string;
  model_fallback_used: boolean;
  cost_estimate_usd?: number | null;
  started_at?: string | null;
  ended_at?: string | null;
  duration_ms?: number | null;
  result_summary: string;
  artifacts: Record<string, string>;
  error_message: string;
}

export interface SubagentTaskListResponse {
  items: SubagentTask[];
  total: number;
  limit: number;
  offset: number;
}

export interface SubagentTaskEvent {
  event_id: string;
  task_id: string;
  ts: string;
  type: SubagentTaskEventType;
  summary: string;
  status?: SubagentTaskStatus | null;
  payload: Record<string, unknown>;
}

export interface SubagentTaskEventListResponse {
  task_id: string;
  items: SubagentTaskEvent[];
}

export interface SubagentModelOption {
  id: string;
  name: string;
}

export interface SubagentModelProviderOption {
  id: string;
  name: string;
  is_local: boolean;
  has_api_key: boolean;
  models: SubagentModelOption[];
}

export interface SubagentRoleModelOptionsResponse {
  active_provider_id: string;
  active_model: string;
  providers: SubagentModelProviderOption[];
}
