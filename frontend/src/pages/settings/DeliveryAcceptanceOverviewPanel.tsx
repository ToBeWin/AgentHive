import { Bot, Boxes, Brain, Image, KeyRound, type LucideIcon, Route, ShieldCheck } from "lucide-react";
import { cx, Panel, StatusBadge } from "../../components/app-ui";
import type { SystemDiagnostics } from "../../hooks/admin/system";
import { useLocale } from "../../i18n-context";
import type { SystemComponentReport } from "../../lib/api";
import { deliveryStatusLabel, localizedDeliverySummary } from "./settingsUtils";

type AcceptanceState = "done" | "review" | "blocked";

interface AcceptanceGate {
  detail: string;
  evidence: string;
  icon: LucideIcon;
  id: string;
  metric: string;
  state: AcceptanceState;
  title: string;
}

export function DeliveryAcceptanceOverviewPanel({ diagnostics }: { diagnostics: SystemDiagnostics | null }) {
  const { t } = useLocale();
  const readiness = diagnostics?.readiness ?? null;
  const delivery = readiness?.delivery ?? null;
  const components = readiness?.components ?? {};
  const connection = diagnostics?.connection_acceptance ?? null;
  const knowledge = diagnostics?.knowledge_acceptance ?? null;
  const gates = buildGates(components, connection, knowledge, t);
  const doneCount = gates.filter((gate) => gate.state === "done").length;
  const blockedCount = gates.filter((gate) => gate.state === "blocked").length;
  const reviewCount = gates.filter((gate) => gate.state === "review").length;
  const score = gates.length ? Math.round((doneCount / gates.length) * 100) : 0;

  return (
    <Panel
      title={t("settingsAcceptanceOverview")}
      subtitle={t("settingsAcceptanceOverviewHelp")}
      actions={
        <StatusBadge
          status={blockedCount ? "unhealthy" : reviewCount ? "degraded" : "healthy"}
          label={delivery ? deliveryStatusLabel(delivery.status, t) : `${score}%`}
        />
      }
      className="settings-acceptance-overview"
    >
      <div className="settings-acceptance-overview-hero">
        <div>
          <span>{t("settingsAcceptanceOverviewScore")}</span>
          <strong>{score}%</strong>
          <p>
            {delivery
              ? localizedDeliverySummary(delivery, t)
              : t("settingsAcceptanceOverviewSummary")
                  .replace("{{done}}", String(doneCount))
                  .replace("{{total}}", String(gates.length))}
          </p>
        </div>
        <div className="settings-acceptance-overview-counts">
          <span>
            <strong>{doneCount}</strong>
            {t("settingsAcceptanceOverviewPassed")}
          </span>
          <span>
            <strong>{reviewCount}</strong>
            {t("settingsAcceptanceOverviewReview")}
          </span>
          <span>
            <strong>{blockedCount}</strong>
            {t("settingsAcceptanceOverviewBlocked")}
          </span>
        </div>
      </div>
      <div className="settings-acceptance-overview-grid">
        {gates.map((gate) => {
          const Icon = gate.icon;
          return (
            <article className={cx("settings-acceptance-gate", `settings-acceptance-gate-${gate.state}`)} key={gate.id}>
              <span className="settings-acceptance-gate-icon">
                <Icon size={18} />
              </span>
              <div>
                <span>{gate.title}</span>
                <strong>{gate.metric}</strong>
                <p>{gate.detail}</p>
                <small>{gate.evidence}</small>
              </div>
              <StatusBadge status={statusForState(gate.state)} label={labelForState(gate.state, t)} />
            </article>
          );
        })}
      </div>
    </Panel>
  );
}

function buildGates(
  components: Record<string, SystemComponentReport>,
  connection: SystemDiagnostics["connection_acceptance"] | null,
  knowledge: SystemDiagnostics["knowledge_acceptance"] | null,
  t: (key: string) => string,
): AcceptanceGate[] {
  const mediaLiveProbes = connection?.media_live_probe_count ?? 0;
  const modelLiveCalls = connection?.live_network_call_count ?? 0;
  const knowledgeSources = knowledge?.runs_with_sources_count ?? 0;

  return [
    {
      detail: t("settingsAcceptanceGateStackDetail"),
      evidence: componentEvidence(components, ["database", "redis", "minio", "production_config"], t),
      icon: Boxes,
      id: "stack",
      metric: t("settingsAcceptanceGateStackMetric"),
      state: stateFromComponents(components, ["database", "redis", "minio", "production_config"]),
      title: t("settingsAcceptanceGateStack"),
    },
    {
      detail: t("settingsAcceptanceGateLicenseDetail"),
      evidence: componentEvidence(components, ["license_identity"], t),
      icon: KeyRound,
      id: "license",
      metric: t("settingsAcceptanceGateLicenseMetric"),
      state: stateFromComponents(components, ["license_identity"]),
      title: t("settingsAcceptanceGateLicense"),
    },
    {
      detail: t("settingsAcceptanceGateModelsDetail"),
      evidence: t("settingsAcceptanceGateModelsEvidence")
        .replace("{{calls}}", String(modelLiveCalls))
        .replace("{{failed}}", String(connection?.failed_recent_count ?? 0)),
      icon: Brain,
      id: "models",
      metric: t("settingsAcceptanceGateModelsMetric").replace(
        "{{providers}}",
        String(connection?.providers.length ?? 0),
      ),
      state: modelLiveCalls > 0 ? "done" : stateFromComponents(components, ["litellm"]),
      title: t("settingsAcceptanceGateModels"),
    },
    {
      detail: t("settingsAcceptanceGateAgentsDetail"),
      evidence: t("settingsAcceptanceGateAgentsEvidence")
        .replace("{{runs}}", String(knowledge?.knowledge_enabled_run_count ?? 0))
        .replace("{{sources}}", String(knowledgeSources)),
      icon: Bot,
      id: "agents",
      metric: t("settingsAcceptanceGateAgentsMetric").replace("{{agents}}", String(knowledge?.agents.length ?? 0)),
      state: knowledgeSources > 0 ? "done" : stateFromComponents(components, ["knowledge_runtime", "pgvector"]),
      title: t("settingsAcceptanceGateAgents"),
    },
    {
      detail: t("settingsAcceptanceGateChannelsDetail"),
      evidence: componentEvidence(components, ["channel_gateway"], t),
      icon: Route,
      id: "channels",
      metric: t("settingsAcceptanceGateChannelsMetric"),
      state: stateFromComponents(components, ["channel_gateway"]),
      title: t("settingsAcceptanceGateChannels"),
    },
    {
      detail: t("settingsAcceptanceGateGovernanceDetail"),
      evidence: componentEvidence(components, ["budget_governance", "audit_diagnostics"], t),
      icon: ShieldCheck,
      id: "governance",
      metric: t("settingsAcceptanceGateGovernanceMetric"),
      state: stateFromComponents(components, ["budget_governance", "audit_diagnostics"]),
      title: t("settingsAcceptanceGateGovernance"),
    },
    {
      detail: t("settingsAcceptanceGateMediaDetail"),
      evidence: t("settingsAcceptanceGateMediaEvidence").replace("{{probes}}", String(mediaLiveProbes)),
      icon: Image,
      id: "media",
      metric: t("settingsAcceptanceGateMediaMetric"),
      state: mediaLiveProbes > 0 ? "done" : stateFromComponents(components, ["media_generation", "media_worker"]),
      title: t("settingsAcceptanceGateMedia"),
    },
  ];
}

function componentEvidence(
  components: Record<string, SystemComponentReport>,
  keys: string[],
  t: (key: string) => string,
) {
  const reports = keys.map((key) => components[key]).filter(Boolean);
  if (!reports.length) {
    return t("settingsAcceptanceGateEvidenceMissing");
  }
  return reports.map((report) => report.message || report.status).join(" ");
}

function stateFromComponents(components: Record<string, SystemComponentReport>, keys: string[]): AcceptanceState {
  const reports = keys.map((key) => components[key]).filter(Boolean);
  if (!reports.length) {
    return "review";
  }
  if (reports.some((report) => report.status === "unhealthy" || report.status === "error")) {
    return "blocked";
  }
  if (reports.some((report) => report.status === "degraded" || report.status === "not_configured")) {
    return "review";
  }
  return "done";
}

function labelForState(state: AcceptanceState, t: (key: string) => string) {
  if (state === "done") {
    return t("settingsChecklistDone");
  }
  if (state === "blocked") {
    return t("settingsChecklistBlocked");
  }
  return t("settingsChecklistReview");
}

function statusForState(state: AcceptanceState) {
  if (state === "done") {
    return "healthy";
  }
  if (state === "blocked") {
    return "unhealthy";
  }
  return "degraded";
}
