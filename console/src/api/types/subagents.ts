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
