import { request } from "../request";
import type {
  SubagentRoleModelOptionsResponse,
  SubagentsConfig,
  SubagentTask,
  SubagentTaskEventListResponse,
  SubagentTaskListResponse,
} from "../types";

export const subagentsApi = {
  getSubagentsConfig: () => request<SubagentsConfig>("/agent/subagents/config"),

  updateSubagentsConfig: (config: SubagentsConfig) =>
    request<SubagentsConfig>("/agent/subagents/config", {
      method: "PUT",
      body: JSON.stringify(config),
    }),

  listSubagentTasks: (params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    if (typeof params?.limit === "number") {
      query.set("limit", String(params.limit));
    }
    if (typeof params?.offset === "number") {
      query.set("offset", String(params.offset));
    }
    const queryString = query.toString();
    const path = queryString
      ? `/agent/subagents/tasks?${queryString}`
      : "/agent/subagents/tasks";
    return request<SubagentTaskListResponse>(path);
  },

  getSubagentTask: (taskId: string) =>
    request<SubagentTask>(`/agent/subagents/tasks/${encodeURIComponent(taskId)}`),

  getSubagentTaskEvents: (taskId: string) =>
    request<SubagentTaskEventListResponse>(
      `/agent/subagents/tasks/${encodeURIComponent(taskId)}/events`,
    ),

  getSubagentRoleModelOptions: () =>
    request<SubagentRoleModelOptionsResponse>(
      "/agent/subagents/roles/model-options",
    ),

  cancelSubagentTask: (taskId: string) =>
    request<SubagentTask>(
      `/agent/subagents/tasks/${encodeURIComponent(taskId)}/cancel`,
      {
        method: "POST",
      },
    ),
};
