import { request } from "../request";
import type {
  ChannelConfig,
  ShowToolDetailsConfig,
  SingleChannelConfig,
} from "../types";

export const channelApi = {
  listChannelTypes: () => request<string[]>("/config/channels/types"),

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
};
