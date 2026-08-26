import { Bot, CheckCircle2, CircleDollarSign, DatabaseZap, Eye, PackageCheck, Route, Waypoints } from "lucide-react";
import { useState } from "react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type {
  AgentCatalogEntryResponse,
  AgentInstanceResponse,
  BudgetPolicyResponse,
  ChannelResponse,
} from "../../lib/api";
import {
  type AgentKnowledgeBaseOption,
  type AgentModelDeploymentOption,
  knowledgeBaseIdsFromConfig,
} from "./agentInstanceUtils";

type AgentInstanceWorkspaceTab = "create" | "published" | "readiness";
type AgentRolloutStageId =
  | "modules"
  | "instances"
  | "knowledge"
  | "model"
  | "budget"
  | "channel"
  | "exposure"
  | "runtime";

interface AgentRolloutLoopPanelProps {
  budgetPolicies: BudgetPolicyResponse[];
  catalog: AgentCatalogEntryResponse[];
  channels: ChannelResponse[];
  instances: AgentInstanceResponse[];
  knowledgeBases: AgentKnowledgeBaseOption[];
  modelDeployments: AgentModelDeploymentOption[];
  onOpenBudgets: () => void;
  onOpenChannels: () => void;
  onOpenCatalog: () => void;
  onRunInstance: (instance: AgentInstanceResponse) => void;
  onSelectWorkspaceTab: (tab: AgentInstanceWorkspaceTab) => void;
  workspaceTab: AgentInstanceWorkspaceTab;
}

export function AgentRolloutLoopPanel({
  budgetPolicies,
  catalog,
  channels,
  instances,
  knowledgeBases,
  modelDeployments,
  onOpenBudgets,
  onOpenChannels,
  onOpenCatalog,
  onRunInstance,
  onSelectWorkspaceTab,
  workspaceTab,
}: AgentRolloutLoopPanelProps) {
  const { t } = useLocale();
  const installedModules = catalog.filter((agent) => agent.installed).length;
  const enabledModules = catalog.filter((agent) => agent.enabled).length;
  const activeInstances = instances.filter((instance) => instance.status === "active");
  const runnableInstances = activeInstances.filter((instance) => instance.runnable !== false);
  const visibleInstances = activeInstances.filter((instance) => instance.visibility !== "private");
  const withKnowledge = instances.filter((instance) => knowledgeBaseIdsFromConfig(instance.config).length > 0).length;
  const knownKnowledgeIds = new Set(knowledgeBases.map((base) => base.id));
  const staleKnowledge = instances.filter((instance) =>
    knowledgeBaseIdsFromConfig(instance.config).some((id) => !knownKnowledgeIds.has(id)),
  ).length;
  const withRoute = instances.filter((instance) => Boolean(instance.model_routing_key || instance.model_key)).length;
  const modelUnavailable = instances.filter((instance) => instance.model_available === false).length;
  const configuredRoutes = modelDeployments.filter((deployment) => deployment.routing_key).length;
  const budgetCoverage = getBudgetCoverage(instances, budgetPolicies);
  const channelCoverage = getChannelCoverage(instances, channels);
  const runnableInstance = runnableInstances[0] ?? activeInstances[0] ?? instances[0] ?? null;
  const stages: Array<{
    action: () => void;
    detail: string;
    icon: typeof PackageCheck;
    id: AgentRolloutStageId;
    metric: string;
    status: string;
    title: string;
    tone: "ok" | "warning" | "blocked";
  }> = [
    {
      action: onOpenCatalog,
      detail: t("agentsRolloutModulesDetail").replace("{{enabled}}", String(enabledModules)),
      icon: PackageCheck,
      id: "modules",
      metric: t("agentsRolloutModulesMetric")
        .replace("{{installed}}", String(installedModules))
        .replace("{{total}}", String(catalog.length)),
      status: installedModules ? t("agentsRolloutReady") : t("agentsRolloutNeedsModule"),
      title: t("agentsRolloutModules"),
      tone: installedModules ? "ok" : "blocked",
    },
    {
      action: () => onSelectWorkspaceTab(instances.length ? "published" : "create"),
      detail: t("agentsRolloutInstancesDetail").replace("{{active}}", String(activeInstances.length)),
      icon: Bot,
      id: "instances",
      metric: t("agentsRolloutInstancesMetric").replace("{{count}}", String(instances.length)),
      status: activeInstances.length ? t("agentsRolloutReady") : t("agentsRolloutNeedsInstance"),
      title: t("agentsRolloutInstances"),
      tone: activeInstances.length ? "ok" : instances.length ? "warning" : "blocked",
    },
    {
      action: () => onSelectWorkspaceTab("readiness"),
      detail: t("agentsRolloutKnowledgeDetail").replace("{{stale}}", String(staleKnowledge)),
      icon: DatabaseZap,
      id: "knowledge",
      metric: t("agentsRolloutKnowledgeMetric").replace("{{count}}", String(withKnowledge)),
      status: withKnowledge && !staleKnowledge ? t("agentsRolloutReady") : t("agentsRolloutNeedsBinding"),
      title: t("agentsRolloutKnowledge"),
      tone: withKnowledge && !staleKnowledge ? "ok" : withKnowledge ? "warning" : "blocked",
    },
    {
      action: () => onSelectWorkspaceTab("published"),
      detail: t("agentsRolloutModelDetail")
        .replace("{{configured}}", String(configuredRoutes))
        .replace("{{unavailable}}", String(modelUnavailable)),
      icon: Route,
      id: "model",
      metric: t("agentsRolloutModelMetric").replace("{{count}}", String(withRoute)),
      status: withRoute && !modelUnavailable ? t("agentsRolloutReady") : t("agentsRolloutNeedsModel"),
      title: t("agentsRolloutModel"),
      tone: withRoute ? (modelUnavailable ? "warning" : "ok") : configuredRoutes ? "warning" : "blocked",
    },
    {
      action: onOpenBudgets,
      detail: t("agentsRolloutBudgetDetail")
        .replace("{{active}}", String(budgetCoverage.active))
        .replace("{{warning}}", String(budgetCoverage.warning))
        .replace("{{exceeded}}", String(budgetCoverage.exceeded)),
      icon: CircleDollarSign,
      id: "budget",
      metric: t("agentsRolloutBudgetMetric").replace("{{count}}", String(budgetCoverage.covering)),
      status: budgetCoverage.covering ? t("agentsRolloutReady") : t("agentsRolloutNeedsBudget"),
      title: t("agentsRolloutBudget"),
      tone: budgetCoverage.covering
        ? budgetCoverage.exceeded
          ? "blocked"
          : budgetCoverage.warning
            ? "warning"
            : "ok"
        : "blocked",
    },
    {
      action: onOpenChannels,
      detail: t("agentsRolloutChannelDetail")
        .replace("{{active}}", String(channelCoverage.active))
        .replace("{{signed}}", String(channelCoverage.signed)),
      icon: Waypoints,
      id: "channel",
      metric: t("agentsRolloutChannelMetric").replace("{{count}}", String(channelCoverage.bound)),
      status: channelCoverage.bound ? t("agentsRolloutReady") : t("agentsRolloutNeedsChannel"),
      title: t("agentsRolloutChannel"),
      tone: channelCoverage.bound ? (channelCoverage.unsigned ? "warning" : "ok") : "blocked",
    },
    {
      action: () => onSelectWorkspaceTab("published"),
      detail: t("agentsRolloutExposureDetail").replace("{{active}}", String(activeInstances.length)),
      icon: Eye,
      id: "exposure",
      metric: t("agentsRolloutExposureMetric").replace("{{count}}", String(visibleInstances.length)),
      status: visibleInstances.length ? t("agentsRolloutReady") : t("agentsRolloutNeedsExposure"),
      title: t("agentsRolloutExposure"),
      tone: visibleInstances.length ? "ok" : activeInstances.length ? "warning" : "blocked",
    },
    {
      action: () => (runnableInstance ? onRunInstance(runnableInstance) : onSelectWorkspaceTab("readiness")),
      detail: t("agentsRolloutRuntimeDetail").replace("{{unavailable}}", String(modelUnavailable)),
      icon: Route,
      id: "runtime",
      metric: t("agentsRolloutRuntimeMetric").replace("{{count}}", String(runnableInstances.length)),
      status: runnableInstances.length ? t("agentsRolloutReady") : t("agentsRolloutNeedsTest"),
      title: t("agentsRolloutRuntime"),
      tone: runnableInstances.length && !modelUnavailable ? "ok" : runnableInstances.length ? "warning" : "blocked",
    },
  ];
  const workspaceStage: Partial<Record<AgentInstanceWorkspaceTab, AgentRolloutStageId>> = {
    create: "instances",
    published: "instances",
    readiness: "knowledge",
  };
  const preferredStageId =
    stages.find((stage) => stage.tone === "blocked")?.id ??
    stages.find((stage) => stage.tone === "warning")?.id ??
    workspaceStage[workspaceTab] ??
    "runtime";
  const [selectedStageId, setSelectedStageId] = useState<AgentRolloutStageId>(() => preferredStageId);
  const selectedStage = stages.find((stage) => stage.id === selectedStageId) ?? stages[0];
  const SelectedIcon = selectedStage.icon;
  const readyCount = stages.filter((stage) => stage.tone === "ok").length;
  const reviewCount = stages.filter((stage) => stage.tone === "warning").length;
  const blockedCount = stages.filter((stage) => stage.tone === "blocked").length;

  return (
    <details className="agent-rollout-loop" aria-label={t("agentsRolloutTitle")}>
      <summary className="agent-rollout-loop-summary">
        <div>
          <span>{t("agentsRolloutEyebrow")}</span>
          <strong>{t("agentsRolloutTitle")}</strong>
          <small>{t("agentsRolloutCollapseHint")}</small>
        </div>
        <div className="agent-rollout-loop-summary-status">
          <StatusBadge status={t("agentsRolloutReadyCount").replace("{{count}}", String(readyCount))} />
          {reviewCount > 0 && (
            <StatusBadge status={t("agentsRolloutReviewCount").replace("{{count}}", String(reviewCount))} />
          )}
          {blockedCount > 0 && (
            <StatusBadge status={t("agentsRolloutBlockedCount").replace("{{count}}", String(blockedCount))} />
          )}
        </div>
      </summary>
      <p className="agent-rollout-loop-description">{t("agentsRolloutDescription")}</p>
      <div className="agent-rollout-loop-workspace">
        <div className="agent-rollout-loop-steps" role="tablist" aria-label={t("agentsRolloutStageTabs")}>
          {stages.map((stage) => {
            const Icon = stage.icon;
            return (
              <button
                aria-selected={stage.id === selectedStage.id}
                className={cx("agent-rollout-loop-step", stage.tone, stage.id === selectedStage.id && "selected")}
                key={stage.id}
                onClick={() => setSelectedStageId(stage.id)}
                role="tab"
                type="button"
              >
                <span className="agent-rollout-loop-index">
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
        <div className={cx("agent-rollout-loop-detail", selectedStage.tone)} role="tabpanel">
          <div className="agent-rollout-loop-detail-head">
            <span className="agent-rollout-loop-icon">
              <SelectedIcon size={18} />
            </span>
            <div>
              <span>{t("agentsRolloutSelectedStage")}</span>
              <strong>{selectedStage.title}</strong>
              <small>{selectedStage.detail}</small>
            </div>
            <StatusBadge status={selectedStage.status} />
          </div>
          <div className="agent-rollout-loop-detail-metric">
            <span>{t("agentsRolloutCurrentMetric")}</span>
            <strong>{selectedStage.metric}</strong>
          </div>
          <button className="button" onClick={selectedStage.action} type="button">
            {t("agentsRolloutOpenStep")}
          </button>
        </div>
      </div>
      {instances.length > 0 && runnableInstances.length === 0 && (
        <div className="agent-rollout-loop-note">
          <CheckCircle2 size={15} />
          <span>{t("agentsRolloutRuntimeBlockedHint")}</span>
        </div>
      )}
    </details>
  );
}

function getBudgetCoverage(instances: AgentInstanceResponse[], policies: BudgetPolicyResponse[]) {
  const activePolicies = policies.filter((policy) => policy.status === "active");
  const agentIds = new Set(instances.map((instance) => instance.id));
  const departmentIds = new Set(
    instances.map((instance) => instance.department_id).filter((id): id is string => Boolean(id)),
  );
  const coveringPolicies = activePolicies.filter((policy) => {
    if (policy.scope_type === "tenant") {
      return true;
    }
    if (policy.scope_type === "agent" && policy.scope_id && agentIds.has(policy.scope_id)) {
      return true;
    }
    if (policy.scope_type === "department" && policy.scope_id && departmentIds.has(policy.scope_id)) {
      return true;
    }
    return false;
  });

  return {
    active: activePolicies.length,
    covering: coveringPolicies.length,
    exceeded: coveringPolicies.filter((policy) => policy.health === "exceeded").length,
    warning: coveringPolicies.filter((policy) => policy.health === "warning").length,
  };
}

function getChannelCoverage(instances: AgentInstanceResponse[], channels: ChannelResponse[]) {
  const agentIds = new Set(instances.map((instance) => instance.id));
  const activeChannels = channels.filter((channel) => channel.status === "active");
  const boundChannels = activeChannels.filter((channel) => channel.agent_id && agentIds.has(channel.agent_id));
  return {
    active: activeChannels.length,
    bound: boundChannels.length,
    signed: boundChannels.filter((channel) => channel.secret_configured).length,
    unsigned: boundChannels.filter((channel) => !channel.secret_configured).length,
  };
}
