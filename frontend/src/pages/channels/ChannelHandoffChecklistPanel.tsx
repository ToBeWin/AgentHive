import { Bot, ClipboardCheck, KeyRound, type LucideIcon, Network, SendHorizontal, ShieldCheck } from "lucide-react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { AgentInstanceResponse, ChannelProcessingResult, ChannelResponse } from "../../lib/api";
import { channelTypes, getChannelLabel, isChannelTypeLicensed } from "./channelUtils";

interface ChannelHandoffChecklistPanelProps {
  agentInstances: AgentInstanceResponse[];
  channels: ChannelResponse[];
  enabledFeatures: Set<string>;
  licenseLoading: boolean;
  onOpenConfig: () => void;
  onOpenReadiness: () => void;
  onOpenRouteReview: () => void;
  onOpenTest: () => void;
  selectedChannel: ChannelResponse | null;
  testProcessing: ChannelProcessingResult | null;
}

type ChecklistState = "ok" | "warning" | "blocked";

interface ChecklistItem {
  detail: string;
  icon: LucideIcon;
  id: string;
  metric: string;
  onClick: () => void;
  state: ChecklistState;
  status: string;
  title: string;
}

export function ChannelHandoffChecklistPanel({
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
}: ChannelHandoffChecklistPanelProps) {
  const { t } = useLocale();
  const activeChannels = channels.filter((channel) => channel.status === "active");
  const activeAgentIds = new Set(agentInstances.filter((agent) => agent.status === "active").map((agent) => agent.id));
  const licensedLabels = channelTypes
    .filter((type) => isChannelTypeLicensed(type, enabledFeatures))
    .map((type) => getChannelLabel(type));
  const signedChannels = activeChannels.filter((channel) => channel.secret_configured);
  const routedChannels = activeChannels.filter((channel) => {
    const configAgentKey = typeof channel.config.agent_key === "string" ? channel.config.agent_key : "";
    return Boolean((channel.agent_id && activeAgentIds.has(channel.agent_id)) || configAgentKey);
  });
  const staleRoutes = activeChannels.filter(
    (channel) => channel.agent_id && !activeAgentIds.has(channel.agent_id) && !channel.config.agent_key,
  );
  const testPassed = Boolean(testProcessing?.routed && testProcessing.response_text);
  const testTarget = selectedChannel?.name ?? t("channelsLoopTestUnverified");
  const allReady =
    licensedLabels.length > 0 &&
    activeChannels.length > 0 &&
    signedChannels.length > 0 &&
    routedChannels.length > 0 &&
    testPassed;

  const items: ChecklistItem[] = [
    {
      detail: licenseLoading
        ? t("channelsChecklistLicenseChecking")
        : t("channelsChecklistLicenseDetail").replace(
            "{{types}}",
            licensedLabels.length ? licensedLabels.join(", ") : t("channelsLoopNeedsLicense"),
          ),
      icon: ShieldCheck,
      id: "license",
      metric: t("channelsChecklistLicenseMetric").replace("{{count}}", String(licensedLabels.length)),
      onClick: onOpenReadiness,
      state: licenseLoading ? "warning" : licensedLabels.length ? "ok" : "blocked",
      status: licenseLoading
        ? t("channelsChecklistChecking")
        : licensedLabels.length
          ? t("channelsChecklistPassed")
          : t("channelsChecklistBlocked"),
      title: t("channelsChecklistLicense"),
    },
    {
      detail: t("channelsChecklistChannelDetail")
        .replace("{{total}}", String(channels.length))
        .replace("{{active}}", String(activeChannels.length)),
      icon: Network,
      id: "channel",
      metric: t("channelsChecklistChannelMetric").replace("{{count}}", String(activeChannels.length)),
      onClick: onOpenConfig,
      state: activeChannels.length ? "ok" : channels.length ? "warning" : "blocked",
      status: activeChannels.length ? t("channelsChecklistPassed") : t("channelsChecklistNeedsFix"),
      title: t("channelsChecklistChannel"),
    },
    {
      detail: t("channelsChecklistSecretDetail")
        .replace("{{signed}}", String(signedChannels.length))
        .replace("{{active}}", String(activeChannels.length)),
      icon: KeyRound,
      id: "secret",
      metric: t("channelsChecklistSecretMetric").replace("{{count}}", String(signedChannels.length)),
      onClick: onOpenConfig,
      state: signedChannels.length ? "ok" : activeChannels.length ? "warning" : "blocked",
      status: signedChannels.length ? t("channelsChecklistPassed") : t("channelsChecklistNeedsFix"),
      title: t("channelsChecklistSecret"),
    },
    {
      detail: t("channelsChecklistRouteDetail")
        .replace("{{routed}}", String(routedChannels.length))
        .replace("{{stale}}", String(staleRoutes.length))
        .replace("{{agents}}", String(activeAgentIds.size)),
      icon: Bot,
      id: "route",
      metric: t("channelsChecklistRouteMetric").replace("{{count}}", String(routedChannels.length)),
      onClick: onOpenRouteReview,
      state: routedChannels.length && staleRoutes.length === 0 ? "ok" : routedChannels.length ? "warning" : "blocked",
      status: routedChannels.length ? t("channelsChecklistPassed") : t("channelsChecklistNeedsFix"),
      title: t("channelsChecklistRoute"),
    },
    {
      detail: t("channelsChecklistTestDetail").replace("{{channel}}", testTarget),
      icon: SendHorizontal,
      id: "test",
      metric: testPassed ? t("channelsChecklistTestMetricReady") : t("channelsChecklistTestMetricMissing"),
      onClick: onOpenTest,
      state: testPassed ? "ok" : selectedChannel ? "warning" : "blocked",
      status: testPassed ? t("channelsChecklistPassed") : t("channelsChecklistNeedsTest"),
      title: t("channelsChecklistTest"),
    },
  ];

  return (
    <section className="channel-handoff-checklist">
      <div className="channel-handoff-checklist-head">
        <span className="channel-handoff-checklist-icon">
          <ClipboardCheck size={18} />
        </span>
        <div>
          <span>{t("channelsChecklistEyebrow")}</span>
          <strong>{t("channelsChecklistTitle")}</strong>
          <p>{t("channelsChecklistDescription")}</p>
        </div>
        <StatusBadge
          label={allReady ? t("channelsChecklistReady") : t("channelsChecklistNeedsReview")}
          status={allReady ? "ready" : "warning"}
        />
      </div>
      <div className="channel-handoff-checklist-grid">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <button
              className={cx("channel-handoff-checklist-card", item.state)}
              key={item.id}
              onClick={item.onClick}
              type="button"
            >
              <span className="channel-handoff-checklist-card-icon">
                <Icon size={17} />
              </span>
              <span className="channel-handoff-checklist-copy">
                <span>{item.title}</span>
                <strong>{item.metric}</strong>
                <small>{item.detail}</small>
                <StatusBadge
                  label={item.status}
                  status={item.state === "ok" ? "ready" : item.state === "warning" ? "warning" : "inactive"}
                />
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
