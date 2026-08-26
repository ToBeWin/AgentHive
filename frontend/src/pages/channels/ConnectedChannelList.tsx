import { ChannelListPanel } from "./ChannelListPanel";
import type { ChannelListWorkspaceProps } from "./channelWorkspaceTypes";

export function ConnectedChannelList({
  agentInstances,
  canWrite,
  channels,
  error,
  loading,
  onRetry,
  onSelect,
  onStatusChange,
  selectedChannel,
  statusUpdatingId,
}: ChannelListWorkspaceProps) {
  return (
    <ChannelListPanel
      agentInstances={agentInstances}
      canWrite={canWrite}
      channels={channels}
      error={error}
      loading={loading}
      onRetry={onRetry}
      onSelect={onSelect}
      onStatusChange={onStatusChange}
      selectedChannel={selectedChannel}
      statusUpdatingId={statusUpdatingId}
    />
  );
}
