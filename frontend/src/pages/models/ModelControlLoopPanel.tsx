import { Activity, KeyRound, Network, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type {
  LLMConnectionTestHistoryItem,
  LLMDeploymentResponse,
  LLMPolicyResponse,
  LLMProviderResponse,
  LLMReadinessResponse,
} from "../../lib/api";
import type { ModelPageTab } from "./useModelsPageController";

interface ModelControlLoopPanelProps {
  activeTab: ModelPageTab;
  connectedCount: number;
  connectionHistory: LLMConnectionTestHistoryItem[];
  deploymentsList: LLMDeploymentResponse[];
  modelReadiness: LLMReadinessResponse | null | undefined;
  onSelectTab: (tab: ModelPageTab) => void;
  policiesList: LLMPolicyResponse[];
  pricesCount: number;
  providersList: LLMProviderResponse[];
}

export function ModelControlLoopPanel({
  activeTab,
  connectedCount,
  connectionHistory,
  deploymentsList,
  modelReadiness,
  onSelectTab,
  policiesList,
  pricesCount,
  providersList,
}: ModelControlLoopPanelProps) {
  const { t } = useLocale();
  const totalProviders = providersList.length;
  const activeDeployments = deploymentsList.filter((deployment) => deployment.status === "active").length;
  const activePolicies = policiesList.filter((policy) => policy.status === "active").length;
  const failedTests = connectionHistory.filter((item) => !item.ok).length;
  const successfulTests = connectionHistory.filter((item) => item.ok).length;
  const readinessCounts = readinessSummary(modelReadiness);
  const stages: Array<{
    detail: string;
    id: ModelPageTab;
    metric: string;
    status: string;
    tone: "ok" | "warning" | "blocked";
    icon: typeof Network;
    title: string;
  }> = [
    {
      detail: t("modelsLoopCoverageDetail").replace("{{routes}}", String(activeDeployments)),
      id: "coverage",
      icon: Network,
      metric: t("modelsLoopProvidersMetric")
        .replace("{{connected}}", String(connectedCount))
        .replace("{{total}}", String(totalProviders)),
      status: connectedCount && activeDeployments ? t("modelsLoopReady") : t("modelsLoopNeedsSetup"),
      title: t("modelsLoopCoverage"),
      tone: connectedCount && activeDeployments ? "ok" : connectedCount ? "warning" : "blocked",
    },
    {
      detail: t("modelsLoopCredentialsDetail").replace("{{connected}}", String(connectedCount)),
      id: "credentials",
      icon: KeyRound,
      metric: t("modelsLoopCredentialsMetric").replace("{{count}}", String(connectedCount)),
      status: connectedCount ? t("modelsLoopReady") : t("modelsLoopNeedsCredential"),
      title: t("modelsLoopCredentials"),
      tone: connectedCount ? "ok" : "blocked",
    },
    {
      detail: t("modelsLoopGovernanceDetail").replace("{{prices}}", String(pricesCount)),
      id: "governance",
      icon: ShieldCheck,
      metric: t("modelsLoopPoliciesMetric").replace("{{count}}", String(activePolicies)),
      status: activePolicies && pricesCount ? t("modelsLoopReady") : t("modelsLoopNeedsPolicy"),
      title: t("modelsLoopGovernance"),
      tone: activePolicies && pricesCount ? "ok" : activePolicies || pricesCount ? "warning" : "blocked",
    },
    {
      detail: t("modelsLoopDiagnosticsDetail")
        .replace("{{ready}}", String(readinessCounts.ready))
        .replace("{{blocked}}", String(readinessCounts.blocked)),
      id: "diagnostics",
      icon: Activity,
      metric: t("modelsLoopDiagnosticsMetric")
        .replace("{{ok}}", String(successfulTests))
        .replace("{{failed}}", String(failedTests)),
      status: failedTests
        ? t("modelsLoopHasFailures")
        : successfulTests
          ? t("modelsLoopReady")
          : t("modelsLoopNoTests"),
      title: t("modelsLoopDiagnostics"),
      tone: failedTests || readinessCounts.blocked ? "warning" : successfulTests ? "ok" : "blocked",
    },
  ];
  const preferredStage =
    stages.find((stage) => stage.tone === "blocked") ??
    stages.find((stage) => stage.tone === "warning") ??
    stages.find((stage) => stage.id === activeTab) ??
    stages[0];
  const [selectedStageId, setSelectedStageId] = useState<ModelPageTab>(() => preferredStage.id);
  const selectedStage = stages.find((stage) => stage.id === selectedStageId) ?? preferredStage;
  const SelectedIcon = selectedStage.icon;
  const readyCount = stages.filter((stage) => stage.tone === "ok").length;
  const reviewCount = stages.filter((stage) => stage.tone === "warning").length;
  const blockedCount = stages.filter((stage) => stage.tone === "blocked").length;

  return (
    <details className="model-control-loop" aria-label={t("modelsLoopTitle")}>
      <summary className="model-control-loop-summary">
        <div>
          <span>{t("modelsLoopEyebrow")}</span>
          <strong>{t("modelsLoopTitle")}</strong>
          <small>{t("modelsLoopCollapseHint")}</small>
        </div>
        <div className="model-control-loop-summary-status">
          <StatusBadge status={t("modelsLoopReadyCount").replace("{{count}}", String(readyCount))} />
          {reviewCount > 0 && (
            <StatusBadge status={t("modelsLoopReviewCount").replace("{{count}}", String(reviewCount))} />
          )}
          {blockedCount > 0 && (
            <StatusBadge status={t("modelsLoopBlockedCount").replace("{{count}}", String(blockedCount))} />
          )}
        </div>
      </summary>
      <p className="model-control-loop-description">{t("modelsLoopDescription")}</p>
      <div className="model-control-loop-workspace">
        <div className="model-control-loop-steps" role="tablist" aria-label={t("modelsLoopStageTabs")}>
          {stages.map((stage) => {
            const Icon = stage.icon;
            return (
              <button
                aria-selected={stage.id === selectedStage.id}
                className={cx(
                  "model-control-loop-step",
                  stage.tone,
                  activeTab === stage.id && "active-workspace",
                  stage.id === selectedStage.id && "selected",
                )}
                key={stage.id}
                onClick={() => setSelectedStageId(stage.id)}
                role="tab"
                type="button"
              >
                <span className="model-control-loop-index">
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
        <div className={cx("model-control-loop-detail", selectedStage.tone)} role="tabpanel">
          <div className="model-control-loop-detail-head">
            <span className="model-control-loop-icon">
              <SelectedIcon size={18} />
            </span>
            <div>
              <span>{t("modelsLoopSelectedStage")}</span>
              <strong>{selectedStage.title}</strong>
              <small>{selectedStage.detail}</small>
            </div>
            <StatusBadge status={selectedStage.status} />
          </div>
          <div className="model-control-loop-detail-metric">
            <span>{t("modelsLoopCurrentMetric")}</span>
            <strong>{selectedStage.metric}</strong>
          </div>
          <button className="button" onClick={() => onSelectTab(selectedStage.id)} type="button">
            {t("modelsLoopOpenStep")}
          </button>
        </div>
      </div>
    </details>
  );
}

function readinessSummary(modelReadiness: LLMReadinessResponse | null | undefined) {
  const summary = modelReadiness?.summary ?? {};
  const ready =
    numericSummary(summary.ready) ||
    modelReadiness?.deployments.filter((item) => item.readiness === "ready").length ||
    0;
  const blocked =
    numericSummary(summary.blocked) ||
    modelReadiness?.deployments.filter((item) => item.readiness === "blocked").length ||
    0;
  return { blocked, ready };
}

function numericSummary(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}
