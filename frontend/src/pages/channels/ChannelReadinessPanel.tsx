import { Bot, CheckCircle2, KeyRound, Network, ShieldCheck, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { AgentInstanceResponse, ChannelResponse } from "../../lib/api";
import { channelTypes, getChannelLabel, isChannelTypeLicensed } from "./channelUtils";

interface ChannelReadinessPanelProps {
  agentInstances: AgentInstanceResponse[];
  channels: ChannelResponse[];
  enabledFeatures: Set<string>;
  licenseLoading: boolean;
}

export function ChannelReadinessPanel({
  agentInstances,
  channels,
  enabledFeatures,
  licenseLoading,
}: ChannelReadinessPanelProps) {
  const { t } = useLocale();
  const readiness = getChannelReadiness(channels, agentInstances, enabledFeatures, licenseLoading, t);
  const Icon = readiness.kind === "ready" ? CheckCircle2 : readiness.kind === "warning" ? TriangleAlert : Network;

  return (
    <section className={cx("channel-readiness-panel", readiness.kind)}>
      <div className="channel-readiness-header">
        <span className="channel-readiness-icon">
          <Icon size={18} />
        </span>
        <div>
          <h2>{t("channelsReadinessTitle")}</h2>
          <p>{readiness.message}</p>
        </div>
        <StatusBadge label={readiness.label} status={readiness.status} />
      </div>
      <div className="channel-readiness-grid">
        <ReadinessMetric icon={<Network size={15} />} label={t("channelsReadinessTotal")} value={readiness.total} />
        <ReadinessMetric
          icon={<CheckCircle2 size={15} />}
          label={t("channelsReadinessActive")}
          value={readiness.active}
        />
        <ReadinessMetric icon={<Bot size={15} />} label={t("channelsReadinessWithAgent")} value={readiness.withAgent} />
        <ReadinessMetric icon={<KeyRound size={15} />} label={t("channelsReadinessSigned")} value={readiness.signed} />
        <ReadinessMetric
          icon={<ShieldCheck size={15} />}
          label={t("channelsReadinessLicensedTypes")}
          value={readiness.licensedTypes}
        />
      </div>
      {readiness.licensedLabels.length > 0 && (
        <div className="channel-readiness-types">
          {readiness.licensedLabels.map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>
      )}
      {readiness.gaps.length > 0 && (
        <div className="channel-readiness-gaps">
          {readiness.gaps.map((gap) => (
            <span key={gap}>{gap}</span>
          ))}
        </div>
      )}
    </section>
  );
}

function ReadinessMetric({ icon, label, value }: { icon: ReactNode; label: string; value: number }) {
  return (
    <div className="channel-readiness-metric">
      <span>
        {icon}
        {label}
      </span>
      <strong>{value}</strong>
    </div>
  );
}

function getChannelReadiness(
  channels: ChannelResponse[],
  agentInstances: AgentInstanceResponse[],
  enabledFeatures: Set<string>,
  licenseLoading: boolean,
  t: (key: string) => string,
) {
  const total = channels.length;
  const active = channels.filter((channel) => channel.status === "active").length;
  const agentIds = new Set(agentInstances.map((agent) => agent.id));
  const withAgent = channels.filter(
    (channel) => Boolean(channel.agent_id && agentIds.has(channel.agent_id)) || Boolean(channel.config.agent_key),
  ).length;
  const signed = channels.filter((channel) => channel.secret_configured).length;
  const licensedLabels = channelTypes
    .filter((type) => isChannelTypeLicensed(type, enabledFeatures))
    .map((type) => getChannelLabel(type));
  const missingAgentBindings = channels.filter(
    (channel) => channel.agent_id && !agentIds.has(channel.agent_id) && !channel.config.agent_key,
  ).length;
  const gaps: string[] = [];

  if (licenseLoading) {
    return {
      active,
      gaps: [t("channelsReadinessLicenseLoading")],
      kind: "empty",
      label: t("channelsReadinessChecking"),
      licensedLabels,
      licensedTypes: licensedLabels.length,
      message: t("channelsReadinessCheckingMessage"),
      signed,
      status: "testing",
      total,
      withAgent,
    };
  }

  if (total === 0) {
    return {
      active,
      gaps,
      kind: "empty",
      label: t("channelsReadinessNotReady"),
      licensedLabels,
      licensedTypes: licensedLabels.length,
      message: t("channelsReadinessCreateFirst"),
      signed,
      status: "inactive",
      total,
      withAgent,
    };
  }

  if (active === 0) {
    gaps.push(t("channelsReadinessGapNoActive"));
  }
  if (withAgent === 0) {
    gaps.push(t("channelsReadinessGapNoAgent"));
  }
  if (signed === 0) {
    gaps.push(t("channelsReadinessGapNoSecret"));
  }
  if (missingAgentBindings > 0) {
    gaps.push(t("channelsReadinessGapStaleAgent").replace("{{count}}", String(missingAgentBindings)));
  }

  if (active > 0 && withAgent > 0 && gaps.length === 0) {
    return {
      active,
      gaps,
      kind: "ready",
      label: t("channelsReadinessReady"),
      licensedLabels,
      licensedTypes: licensedLabels.length,
      message: t("channelsReadinessReadyMessage"),
      signed,
      status: "ready",
      total,
      withAgent,
    };
  }

  return {
    active,
    gaps,
    kind: "warning",
    label: t("channelsReadinessNeedsReview"),
    licensedLabels,
    licensedTypes: licensedLabels.length,
    message: t("channelsReadinessReviewMessage"),
    signed,
    status: "warning",
    total,
    withAgent,
  };
}
