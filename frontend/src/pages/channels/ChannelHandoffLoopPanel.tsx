import { Bot, CheckCircle2, KeyRound, type LucideIcon, Network, SendHorizontal, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { AgentInstanceResponse, ChannelProcessingResult, ChannelResponse } from "../../lib/api";
import { channelTypes, getChannelLabel, isChannelTypeLicensed } from "./channelUtils";
import type { ChannelsPageTab } from "./channelWorkspaceTypes";

type ChannelLoopStageId = "license" | "config" | "route" | "test";

interface ChannelHandoffLoopPanelProps {
  activeTab: ChannelsPageTab;
  agentInstances: AgentInstanceResponse[];
  channels: ChannelResponse[];
  enabledFeatures: Set<string>;
  licenseLoading: boolean;
  onOpenConfig: () => void;
  onOpenRouteReview: () => void;
  onOpenTest: () => void;
  onOpenReadiness: () => void;
  selectedChannel: ChannelResponse | null;
  testProcessing: ChannelProcessingResult | null;
}

export function ChannelHandoffLoopPanel({
  activeTab,
  agentInstances,
  channels,
  enabledFeatures,
  licenseLoading,
  onOpenConfig,
  onOpenReadiness,
  onOpenRouteReview,
  onOpenTest,
  selectedChannel,
  testProcessing,
}: ChannelHandoffLoopPanelProps) {
  const { t } = useLocale();
  const licensedLabels = channelTypes
    .filter((type) => isChannelTypeLicensed(type, enabledFeatures))
    .map((type) => getChannelLabel(type));
  const activeChannels = channels.filter((channel) => channel.status === "active");
  const activeAgentIds = new Set(agentInstances.filter((agent) => agent.status === "active").map((agent) => agent.id));
  const routedChannels = channels.filter(
    (channel) => Boolean(channel.agent_id && activeAgentIds.has(channel.agent_id)) || Boolean(channel.config.agent_key),
  );
  const signedChannels = channels.filter((channel) => channel.secret_configured);
  const testPassed = Boolean(testProcessing?.routed && testProcessing.response_text);
  const stages: Array<{
    action: () => void;
    detail: string;
    icon: LucideIcon;
    id: ChannelLoopStageId;
    metric: string;
    status: string;
    title: string;
    tone: "ok" | "warning" | "blocked";
  }> = [
    {
      action: onOpenReadiness,
      detail: licenseLoading
        ? t("channelsLoopLicenseCheckingDetail")
        : t("channelsLoopLicenseDetail").replace("{{types}}", licensedLabels.slice(0, 3).join(", ") || "-"),
      icon: ShieldCheck,
      id: "license",
      metric: licenseLoading
        ? t("channelsLoopChecking")
        : t("channelsLoopLicenseMetric").replace("{{count}}", String(licensedLabels.length)),
      status: licenseLoading
        ? t("channelsLoopChecking")
        : licensedLabels.length
          ? t("channelsLoopReady")
          : t("channelsLoopNeedsLicense"),
      title: t("channelsLoopLicense"),
      tone: licenseLoading ? "warning" : licensedLabels.length ? "ok" : "blocked",
    },
    {
      action: onOpenConfig,
      detail: t("channelsLoopConfigDetail")
        .replace("{{active}}", String(activeChannels.length))
        .replace("{{signed}}", String(signedChannels.length)),
      icon: Network,
      id: "config",
      metric: t("channelsLoopConfigMetric").replace("{{count}}", String(channels.length)),
      status: activeChannels.length ? t("channelsLoopReady") : t("channelsLoopNeedsChannel"),
      title: t("channelsLoopConfig"),
      tone: activeChannels.length && signedChannels.length ? "ok" : activeChannels.length ? "warning" : "blocked",
    },
    {
      action: onOpenRouteReview,
      detail: t("channelsLoopRouteDetail").replace("{{agents}}", String(agentInstances.length)),
      icon: Bot,
      id: "route",
      metric: t("channelsLoopRouteMetric").replace("{{count}}", String(routedChannels.length)),
      status: routedChannels.length ? t("channelsLoopReady") : t("channelsLoopNeedsAgent"),
      title: t("channelsLoopRoute"),
      tone: routedChannels.length ? "ok" : channels.length ? "warning" : "blocked",
    },
    {
      action: onOpenTest,
      detail: selectedChannel
        ? t("channelsLoopTestDetail").replace("{{channel}}", selectedChannel.name)
        : t("channelsLoopTestMissingDetail"),
      icon: SendHorizontal,
      id: "test",
      metric: testPassed ? t("channelsLoopTestPassed") : t("channelsLoopTestUnverified"),
      status: testPassed ? t("channelsLoopReady") : t("channelsLoopNeedsTest"),
      title: t("channelsLoopTest"),
      tone: testPassed ? "ok" : selectedChannel ? "warning" : "blocked",
    },
  ];
  const preferredStageId =
    stages.find((stage) => stage.tone === "blocked")?.id ??
    stages.find((stage) => stage.tone === "warning")?.id ??
    activeStageId(activeTab);
  const [selectedStageId, setSelectedStageId] = useState<ChannelLoopStageId>(() => preferredStageId);
  const selectedStage = stages.find((stage) => stage.id === selectedStageId) ?? stages[0];
  const SelectedIcon = selectedStage.icon;
  const readyCount = stages.filter((stage) => stage.tone === "ok").length;
  const reviewCount = stages.filter((stage) => stage.tone === "warning").length;
  const blockedCount = stages.filter((stage) => stage.tone === "blocked").length;

  return (
    <details className="channel-handoff-loop" aria-label={t("channelsLoopTitle")}>
      <summary className="channel-handoff-loop-summary">
        <div>
          <span>{t("channelsLoopEyebrow")}</span>
          <strong>{t("channelsLoopTitle")}</strong>
          <small>{t("channelsLoopCollapseHint")}</small>
        </div>
        <div className="channel-handoff-loop-summary-status">
          <StatusBadge status={t("channelsLoopReadyCount").replace("{{count}}", String(readyCount))} />
          {reviewCount > 0 && (
            <StatusBadge status={t("channelsLoopReviewCount").replace("{{count}}", String(reviewCount))} />
          )}
          {blockedCount > 0 && (
            <StatusBadge status={t("channelsLoopBlockedCount").replace("{{count}}", String(blockedCount))} />
          )}
        </div>
      </summary>
      <p className="channel-handoff-loop-description">{t("channelsLoopDescription")}</p>
      <div className="channel-handoff-loop-workspace">
        <div className="channel-handoff-loop-steps" role="tablist" aria-label={t("channelsLoopStageTabs")}>
          {stages.map((stage) => {
            const Icon = stage.icon;
            return (
              <button
                aria-selected={stage.id === selectedStage.id}
                className={cx(
                  "channel-handoff-loop-step",
                  stage.tone,
                  stage.id === activeStageId(activeTab) && "active-workspace",
                  stage.id === selectedStage.id && "selected",
                )}
                key={stage.id}
                onClick={() => setSelectedStageId(stage.id)}
                role="tab"
                type="button"
              >
                <span className="channel-handoff-loop-index">
                  <Icon size={16} />
                </span>
                <span>
                  <strong>{stage.title}</strong>
                  <small>{stage.status}</small>
                </span>
              </button>
            );
          })}
        </div>
        <div className={cx("channel-handoff-loop-detail", selectedStage.tone)} role="tabpanel">
          <div className="channel-handoff-loop-detail-head">
            <span className="channel-handoff-loop-icon">
              <SelectedIcon size={18} />
            </span>
            <div>
              <span>{t("channelsLoopSelectedStage")}</span>
              <strong>{selectedStage.title}</strong>
              <small>{selectedStage.detail}</small>
            </div>
            <StatusBadge status={selectedStage.status} />
          </div>
          <div className="channel-handoff-loop-detail-metric">
            <span>{t("channelsLoopCurrentMetric")}</span>
            <strong>{selectedStage.metric}</strong>
          </div>
          <button className="button" onClick={selectedStage.action} type="button">
            {t("channelsLoopOpenStep")}
          </button>
        </div>
      </div>
      {licensedLabels.length > 0 && activeChannels.length > 0 && routedChannels.length > 0 && testPassed && (
        <div className="channel-handoff-loop-note">
          <CheckCircle2 size={15} />
          <span>{t("channelsLoopReadyHint")}</span>
        </div>
      )}
      {signedChannels.length === 0 && channels.length > 0 && (
        <div className="channel-handoff-loop-note warning">
          <KeyRound size={15} />
          <span>{t("channelsLoopSecretHint")}</span>
        </div>
      )}
    </details>
  );
}

function activeStageId(activeTab: ChannelsPageTab): ChannelLoopStageId {
  if (activeTab === "config") {
    return "config";
  }
  if (activeTab === "test") {
    return "test";
  }
  return "license";
}
