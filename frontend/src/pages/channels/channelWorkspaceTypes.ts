import type { AgentInstanceResponse, ChannelResponse } from "../../lib/api";

export type ChannelsPageTab = "overview" | "config" | "test" | "push";
export type ChannelsOverviewTab = "readiness" | "connected";
export type ChannelsConfigTab = "create" | "connected";
export type ChannelsCreateStep = "type" | "binding";
export type ChannelsTestTab = "endpoint" | "message";

export interface ChannelListWorkspaceProps {
  agentInstances: AgentInstanceResponse[];
  canWrite: boolean;
  channels: ChannelResponse[];
  error: string | null;
  loading: boolean;
  onRetry: () => void;
  onSelect: (channelId: string | null) => void;
  onStatusChange: (channel: ChannelResponse) => void;
  selectedChannel: ChannelResponse | null;
  statusUpdatingId: string | null;
}
