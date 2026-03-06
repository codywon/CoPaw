import { request } from "../request";
import type {
  ChannelConfig,
  ShowToolDetailsConfig,
  ShowReasoningConfig,
  SingleChannelConfig,
  ChannelInstanceSummary,
  ChannelInstanceDetail,
  ChannelInstanceUpsertPayload,
  DeleteResponse,
} from "../types";

export const channelApi = {
  listChannelTypes: () => request<string[]>("/config/channels/types"),
  listChannelInstances: () =>
    request<ChannelInstanceSummary[]>("/config/channels/instances"),
  getChannelInstance: (instanceName: string) =>
    request<ChannelInstanceDetail>(
      `/config/channels/instances/${encodeURIComponent(instanceName)}`,
    ),
  upsertChannelInstance: (
    instanceName: string,
    body: ChannelInstanceUpsertPayload,
  ) =>
    request<ChannelInstanceDetail>(
      `/config/channels/instances/${encodeURIComponent(instanceName)}`,
      {
        method: "PUT",
        body: JSON.stringify(body),
      },
    ),
  deleteChannelInstance: (instanceName: string) =>
    request<DeleteResponse>(
      `/config/channels/instances/${encodeURIComponent(instanceName)}`,
      {
        method: "DELETE",
      },
    ),

  listChannels: () => request<ChannelConfig>("/config/channels"),

  updateChannels: (body: ChannelConfig) =>
    request<ChannelConfig>("/config/channels", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  getChannelConfig: (channelName: string) =>
    request<SingleChannelConfig>(
      `/config/channels/${encodeURIComponent(channelName)}`,
    ),

  updateChannelConfig: (channelName: string, body: SingleChannelConfig) =>
    request<SingleChannelConfig>(
      `/config/channels/${encodeURIComponent(channelName)}`,
      {
        method: "PUT",
        body: JSON.stringify(body),
      },
    ),

  getShowToolDetails: () =>
    request<ShowToolDetailsConfig>("/config/show-tool-details", {
      cache: "no-store",
    }),

  updateShowToolDetails: (showToolDetails: boolean) =>
    request<ShowToolDetailsConfig>("/config/show-tool-details", {
      method: "PUT",
      body: JSON.stringify({ show_tool_details: showToolDetails }),
    }),

  getShowReasoning: () =>
    request<ShowReasoningConfig>("/config/show-reasoning", {
      cache: "no-store",
    }),

  updateShowReasoning: (showReasoning: boolean) =>
    request<ShowReasoningConfig>("/config/show-reasoning", {
      method: "PUT",
      body: JSON.stringify({ show_reasoning: showReasoning }),
    }),
};
