import { Activity, CheckCircle2, KeyRound, type LucideIcon, ReceiptText, Route, ShieldCheck } from "lucide-react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type {
  LLMConnectionTestHistoryItem,
  LLMDeploymentResponse,
  LLMPolicyResponse,
  LLMProviderResponse,
  LLMReadinessResponse,
} from "../../lib/api";

interface ModelHandoffChecklistPanelProps {
  connectionHistory: LLMConnectionTestHistoryItem[];
  deployments: LLMDeploymentResponse[];
  modelReadiness: LLMReadinessResponse | null | undefined;
  onOpenCoverage: () => void;
  onOpenCredentials: () => void;
  onOpenDiagnostics: () => void;
  onOpenGovernance: () => void;
  policies: LLMPolicyResponse[];
  pricesCount: number;
  providers: LLMProviderResponse[];
}

export function ModelHandoffChecklistPanel({
  connectionHistory,
  deployments,
  modelReadiness,
  onOpenCoverage,
  onOpenCredentials,
  onOpenDiagnostics,
  onOpenGovernance,
  policies,
  pricesCount,
  providers,
}: ModelHandoffChecklistPanelProps) {
  const { t } = useLocale();
  const connectedProviders = providers.filter((provider) => provider.credential_configured);
  const activeDeployments = deployments.filter((deployment) => deployment.status === "active");
  const activePolicies = policies.filter((policy) => policy.status === "active");
  const readinessItems = modelReadiness?.deployments ?? [];
  const readyRoutes = readinessItems.filter((deployment) => deployment.readiness === "ready");
  const blockedRoutes = readinessItems.filter((deployment) => deployment.readiness === "blocked");
  const liveEvidenceCount = liveEvidenceKeys(readinessItems, connectionHistory).size;
  const failedTests = connectionHistory.filter((item) => !item.ok).length;
  const hasLiveEvidence = liveEvidenceCount > 0;
  const checks: Array<{
    action: () => void;
    detail: string;
    icon: LucideIcon;
    metric: string;
    status: string;
    title: string;
    tone: "ok" | "warning" | "blocked";
  }> = [
    {
      action: onOpenCredentials,
      detail: t("modelsChecklistCredentialDetail").replace("{{total}}", String(providers.length)),
      icon: KeyRound,
      metric: t("modelsChecklistCredentialMetric").replace("{{count}}", String(connectedProviders.length)),
      status: connectedProviders.length ? t("modelsChecklistPassed") : t("modelsChecklistBlocked"),
      title: t("modelsChecklistCredential"),
      tone: connectedProviders.length ? "ok" : "blocked",
    },
    {
      action: onOpenCoverage,
      detail: t("modelsChecklistRouteDetail").replace("{{ready}}", String(readyRoutes.length)),
      icon: Route,
      metric: t("modelsChecklistRouteMetric").replace("{{count}}", String(activeDeployments.length)),
      status: activeDeployments.length ? t("modelsChecklistPassed") : t("modelsChecklistNeedsFix"),
      title: t("modelsChecklistRoute"),
      tone: activeDeployments.length ? (blockedRoutes.length ? "warning" : "ok") : "blocked",
    },
    {
      action: onOpenGovernance,
      detail: t("modelsChecklistGovernanceDetail").replace("{{prices}}", String(pricesCount)),
      icon: ShieldCheck,
      metric: t("modelsChecklistGovernanceMetric").replace("{{count}}", String(activePolicies.length)),
      status: activePolicies.length && pricesCount ? t("modelsChecklistPassed") : t("modelsChecklistNeedsFix"),
      title: t("modelsChecklistGovernance"),
      tone: activePolicies.length && pricesCount ? "ok" : activePolicies.length || pricesCount ? "warning" : "blocked",
    },
    {
      action: onOpenDiagnostics,
      detail: t("modelsChecklistProbeDetail").replace("{{live}}", String(liveEvidenceCount)),
      icon: CheckCircle2,
      metric: hasLiveEvidence ? t("modelsChecklistProbeMetricReady") : t("modelsChecklistProbeMetricMissing"),
      status: hasLiveEvidence ? t("modelsChecklistPassed") : t("modelsChecklistNeedsTest"),
      title: t("modelsChecklistProbe"),
      tone: hasLiveEvidence ? "ok" : activeDeployments.length ? "warning" : "blocked",
    },
    {
      action: onOpenDiagnostics,
      detail: t("modelsChecklistDiagnosticsDetail").replace("{{failed}}", String(failedTests)),
      icon: Activity,
      metric: t("modelsChecklistDiagnosticsMetric").replace("{{count}}", String(connectionHistory.length)),
      status: failedTests ? t("modelsChecklistNeedsReview") : t("modelsChecklistPassed"),
      title: t("modelsChecklistDiagnostics"),
      tone: failedTests ? "warning" : connectionHistory.length ? "ok" : "blocked",
    },
  ];
  const passed = checks.filter((check) => check.tone === "ok").length;

  return (
    <section className="model-handoff-checklist" aria-label={t("modelsChecklistTitle")}>
      <div className="model-handoff-checklist-head">
        <span className="model-handoff-checklist-icon">
          <ReceiptText size={18} />
        </span>
        <div>
          <span>{t("modelsChecklistEyebrow")}</span>
          <strong>{t("modelsChecklistTitle")}</strong>
          <p>
            {t("modelsChecklistDescription")
              .replace("{{passed}}", String(passed))
              .replace("{{total}}", String(checks.length))}
          </p>
        </div>
        <StatusBadge
          label={passed === checks.length ? t("modelsChecklistReady") : t("modelsChecklistNeedsReview")}
          status={passed === checks.length ? "ready" : "warning"}
        />
      </div>
      <div className="model-handoff-checklist-grid">
        {checks.map((check) => {
          const Icon = check.icon;
          return (
            <button
              className={cx("model-handoff-checklist-card", check.tone)}
              key={check.title}
              onClick={check.action}
              type="button"
            >
              <span className="model-handoff-checklist-card-icon">
                <Icon size={17} />
              </span>
              <span className="model-handoff-checklist-copy">
                <span>{check.title}</span>
                <strong>{check.metric}</strong>
                <small>{check.detail}</small>
              </span>
              <StatusBadge label={check.status} status={check.tone} />
            </button>
          );
        })}
      </div>
    </section>
  );
}

function liveEvidenceKeys(
  readinessItems: LLMReadinessResponse["deployments"],
  connectionHistory: LLMConnectionTestHistoryItem[],
) {
  const keys = new Set<string>();
  for (const deployment of readinessItems) {
    if (!deployment.live_probe_ok) {
      continue;
    }
    const requestId =
      typeof deployment.evidence.last_probe_request_id === "string" ? deployment.evidence.last_probe_request_id : "";
    keys.add(requestId || deployment.deployment_id);
  }
  for (const item of connectionHistory) {
    if (!item.ok || item.live_network_call !== true) {
      continue;
    }
    keys.add(item.request_id || item.deployment_id || item.id);
  }
  return keys;
}
