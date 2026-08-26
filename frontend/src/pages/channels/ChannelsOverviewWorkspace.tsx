import { PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { ChannelProcessingResult } from "../../lib/api";
import { ChannelHandoffChecklistPanel } from "./ChannelHandoffChecklistPanel";
import { ChannelReadinessPanel } from "./ChannelReadinessPanel";
import { ConnectedChannelList } from "./ConnectedChannelList";
import type { ChannelListWorkspaceProps, ChannelsOverviewTab } from "./channelWorkspaceTypes";

export function ChannelsOverviewWorkspace({
  agentInstances,
  canWrite,
  channels,
  enabledFeatures,
  error,
  licenseLoading,
  loading,
  onOpenConfig,
  onOpenReadiness,
  onOpenRouteReview,
  onOpenTest,
  onOverviewTabChange,
  onRetry,
  onSelect,
  onStatusChange,
  overviewTab,
  selectedChannel,
  statusUpdatingId,
  testProcessing,
}: ChannelListWorkspaceProps & {
  enabledFeatures: Set<string>;
  licenseLoading: boolean;
  onOpenConfig: () => void;
  onOpenReadiness: () => void;
  onOpenRouteReview: () => void;
  onOpenTest: () => void;
  onOverviewTabChange: (tab: ChannelsOverviewTab) => void;
  overviewTab: ChannelsOverviewTab;
  testProcessing: ChannelProcessingResult | null;
}) {
  const { t } = useLocale();

  return (
    <div className="nested-workspace channel-overview-workspace">
      <PageTabs
        active={overviewTab}
        onChange={onOverviewTabChange}
        tabs={[
          {
            id: "readiness",
            label: t("channelsOverviewTabReadiness"),
            description: t("channelsOverviewTabReadinessDesc"),
          },
          {
            id: "connected",
            label: t("channelsOverviewTabConnected").replace("{{count}}", String(channels.length)),
            description: t("channelsOverviewTabConnectedDesc"),
          },
        ]}
      />
      {overviewTab === "readiness" && (
        <>
          <ChannelHandoffChecklistPanel
            agentInstances={agentInstances}
            channels={channels}
            enabledFeatures={enabledFeatures}
            licenseLoading={licenseLoading}
            onOpenConfig={onOpenConfig}
            onOpenReadiness={onOpenReadiness}
            onOpenRouteReview={onOpenRouteReview}
            onOpenTest={onOpenTest}
            selectedChannel={selectedChannel}
            testProcessing={testProcessing}
          />
          <ChannelReadinessPanel
            agentInstances={agentInstances}
            channels={channels}
            enabledFeatures={enabledFeatures}
            licenseLoading={licenseLoading}
          />
        </>
      )}
      {overviewTab === "connected" && (
        <ConnectedChannelList
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
      )}
    </div>
  );
}
