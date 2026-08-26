import { CheckCircle2, KeyRound, type LucideIcon, Route, ShieldCheck, Stethoscope } from "lucide-react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type {
  LLMConnectionTestResponse,
  LLMDeploymentAcceptanceTestResponse,
  LLMDeploymentResponse,
  LLMProviderResponse,
} from "../../lib/api";

type CredentialWorkspaceTab = "config" | "routes" | "diagnostics";

interface ModelCredentialProgressPanelProps {
  credentialDraftReady: boolean;
  deploymentsList: LLMDeploymentResponse[];
  lastAcceptanceResult: LLMDeploymentAcceptanceTestResponse | null;
  lastTestResult: LLMConnectionTestResponse | null;
  onSelectTab: (tab: CredentialWorkspaceTab) => void;
  selectedProvider: LLMProviderResponse;
  workspaceTab: CredentialWorkspaceTab;
}

type ProgressTone = "ok" | "warning" | "blocked";

export function ModelCredentialProgressPanel({
  credentialDraftReady,
  deploymentsList,
  lastAcceptanceResult,
  lastTestResult,
  onSelectTab,
  selectedProvider,
  workspaceTab,
}: ModelCredentialProgressPanelProps) {
  const { t } = useLocale();
  const providerKey = selectedProvider.provider_key;
  const credentialConfigured = selectedProvider.credential_configured;
  const routeCount = deploymentsList.length;
  const connectionOk = Boolean(lastTestResult?.ok && lastTestResult.provider_key === providerKey);
  const acceptanceOk = Boolean(lastAcceptanceResult?.ok && lastAcceptanceResult.provider_key === providerKey);
  const steps: Array<{
    detail: string;
    icon: LucideIcon;
    id: string;
    metric: string;
    status: string;
    tab: CredentialWorkspaceTab;
    title: string;
    tone: ProgressTone;
  }> = [
    {
      detail: t("modelsCredentialLoopCredentialDetail"),
      icon: KeyRound,
      id: "credential",
      metric: credentialConfigured
        ? t("modelsCredentialConfigured")
        : credentialDraftReady
          ? t("modelsCredentialLoopReadyToSave")
          : t("modelsCredentialMissing"),
      status: credentialConfigured ? t("modelsChecklistPassed") : t("modelsChecklistNeedsFix"),
      tab: "config",
      title: t("modelsCredentialLoopCredential"),
      tone: credentialConfigured ? "ok" : credentialDraftReady ? "warning" : "blocked",
    },
    {
      detail: t("modelsCredentialLoopRouteDetail"),
      icon: Route,
      id: "routes",
      metric: t("modelsCredentialLoopRouteMetric").replace("{{count}}", String(routeCount)),
      status: routeCount ? t("modelsChecklistPassed") : t("modelsChecklistNeedsFix"),
      tab: "routes",
      title: t("modelsCredentialLoopRoute"),
      tone: routeCount ? "ok" : credentialConfigured ? "warning" : "blocked",
    },
    {
      detail: t("modelsCredentialLoopDiagnosticsDetail"),
      icon: Stethoscope,
      id: "diagnostics",
      metric: connectionOk ? t("modelsConnectionHealthy") : t("modelsLoopNoTests"),
      status: connectionOk ? t("modelsChecklistPassed") : t("modelsChecklistNeedsTest"),
      tab: "diagnostics",
      title: t("modelsCredentialLoopDiagnostics"),
      tone: connectionOk ? "ok" : credentialConfigured ? "warning" : "blocked",
    },
    {
      detail: t("modelsCredentialLoopAcceptanceDetail"),
      icon: ShieldCheck,
      id: "acceptance",
      metric: acceptanceOk ? t("modelsCredentialLoopAccepted") : t("modelsCredentialLoopAcceptancePending"),
      status: acceptanceOk ? t("modelsChecklistPassed") : t("modelsChecklistNeedsTest"),
      tab: "diagnostics",
      title: t("modelsCredentialLoopAcceptance"),
      tone: acceptanceOk ? "ok" : connectionOk ? "warning" : "blocked",
    },
  ];

  return (
    <section className="model-credential-progress" aria-label={t("modelsCredentialLoopTitle")}>
      <div className="model-credential-progress-head">
        <span>{t("modelsCredentialLoopEyebrow")}</span>
        <strong>{t("modelsCredentialLoopTitle")}</strong>
      </div>
      <div className="model-credential-progress-grid">
        {steps.map((step) => {
          const Icon = step.icon;
          const active = workspaceTab === step.tab;
          return (
            <button
              className={cx("model-credential-progress-step", step.tone, active && "active")}
              key={step.id}
              onClick={() => onSelectTab(step.tab)}
              type="button"
            >
              <span className="model-credential-progress-icon">
                {step.tone === "ok" ? <CheckCircle2 size={17} /> : <Icon size={17} />}
              </span>
              <span className="model-credential-progress-copy">
                <span>{step.title}</span>
                <strong>{step.metric}</strong>
                <small>{step.detail}</small>
              </span>
              <StatusBadge label={step.status} status={statusBadgeTone(step.tone)} />
            </button>
          );
        })}
      </div>
    </section>
  );
}

function statusBadgeTone(tone: ProgressTone) {
  if (tone === "ok") {
    return "ready";
  }
  if (tone === "warning") {
    return "degraded";
  }
  return "blocked";
}
