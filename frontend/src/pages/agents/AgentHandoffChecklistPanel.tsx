import {
  Bot,
  CheckCircle2,
  CircleDollarSign,
  DatabaseZap,
  Eye,
  type LucideIcon,
  Route,
  ShieldCheck,
  Waypoints,
} from "lucide-react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { AgentInstanceResponse, BudgetPolicyResponse, ChannelResponse } from "../../lib/api";
import { type AgentKnowledgeBaseOption, knowledgeBaseIdsFromConfig } from "./agentInstanceUtils";

interface AgentHandoffChecklistPanelProps {
  budgetPolicies: BudgetPolicyResponse[];
  channels: ChannelResponse[];
  instances: AgentInstanceResponse[];
  knowledgeBases: AgentKnowledgeBaseOption[];
  onOpenBudgets: () => void;
  onOpenChannels: () => void;
  onCreateInstance: () => void;
  onOpenPublished: () => void;
  onRunInstance: (instance: AgentInstanceResponse) => void;
}

export function AgentHandoffChecklistPanel({
  budgetPolicies,
  channels,
  instances,
  knowledgeBases,
  onOpenBudgets,
  onOpenChannels,
  onCreateInstance,
  onOpenPublished,
  onRunInstance,
}: AgentHandoffChecklistPanelProps) {
  const { t } = useLocale();
  const activeInstances = instances.filter((instance) => instance.status === "active");
  const knownKnowledgeIds = new Set(knowledgeBases.map((base) => base.id));
  const instancesWithKnowledge = instances.filter((instance) => knowledgeBaseIdsFromConfig(instance.config).length > 0);
  const staleKnowledgeInstances = instances.filter((instance) =>
    knowledgeBaseIdsFromConfig(instance.config).some((id) => !knownKnowledgeIds.has(id)),
  );
  const routedInstances = instances.filter((instance) => Boolean(instance.model_routing_key || instance.model_key));
  const availableRouteInstances = instances.filter((instance) =>
    instance.model_available === undefined
      ? Boolean(instance.model_routing_key || instance.model_key)
      : instance.model_available,
  );
  const runnableInstances = activeInstances.filter((instance) =>
    instance.runnable === undefined ? true : instance.runnable,
  );
  const visibleInstances = activeInstances.filter((instance) => instance.visibility !== "private");
  const budgetCoverage = getBudgetCoverage(instances, budgetPolicies);
  const channelCoverage = getChannelCoverage(instances, channels);
  const runtimeTarget = runnableInstances[0] ?? activeInstances[0] ?? instances[0] ?? null;
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
      action: instances.length ? onOpenPublished : onCreateInstance,
      detail: t("agentInstancesChecklistInstanceDetail").replace("{{active}}", String(activeInstances.length)),
      icon: Bot,
      metric: t("agentInstancesChecklistInstanceMetric").replace("{{count}}", String(instances.length)),
      status: activeInstances.length ? t("agentInstancesChecklistPassed") : t("agentInstancesChecklistBlocked"),
      title: t("agentInstancesChecklistInstance"),
      tone: activeInstances.length ? "ok" : "blocked",
    },
    {
      action: onOpenPublished,
      detail: t("agentInstancesChecklistKnowledgeDetail").replace("{{stale}}", String(staleKnowledgeInstances.length)),
      icon: DatabaseZap,
      metric: t("agentInstancesChecklistKnowledgeMetric").replace("{{count}}", String(instancesWithKnowledge.length)),
      status:
        instancesWithKnowledge.length && staleKnowledgeInstances.length === 0
          ? t("agentInstancesChecklistPassed")
          : t("agentInstancesChecklistNeedsFix"),
      title: t("agentInstancesChecklistKnowledge"),
      tone: instancesWithKnowledge.length ? (staleKnowledgeInstances.length === 0 ? "ok" : "warning") : "blocked",
    },
    {
      action: onOpenPublished,
      detail: t("agentInstancesChecklistRouteDetail").replace("{{available}}", String(availableRouteInstances.length)),
      icon: Route,
      metric: t("agentInstancesChecklistRouteMetric").replace("{{count}}", String(routedInstances.length)),
      status: routedInstances.length ? t("agentInstancesChecklistPassed") : t("agentInstancesChecklistNeedsFix"),
      title: t("agentInstancesChecklistRoute"),
      tone: routedInstances.length
        ? availableRouteInstances.length === routedInstances.length
          ? "ok"
          : "warning"
        : "blocked",
    },
    {
      action: onOpenBudgets,
      detail: t("agentInstancesChecklistBudgetDetail")
        .replace("{{active}}", String(budgetCoverage.active))
        .replace("{{warning}}", String(budgetCoverage.warning))
        .replace("{{exceeded}}", String(budgetCoverage.exceeded)),
      icon: CircleDollarSign,
      metric: t("agentInstancesChecklistBudgetMetric").replace("{{count}}", String(budgetCoverage.covering)),
      status: budgetCoverage.covering ? t("agentInstancesChecklistPassed") : t("agentInstancesChecklistNeedsFix"),
      title: t("agentInstancesChecklistBudget"),
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
      detail: t("agentInstancesChecklistChannelDetail")
        .replace("{{active}}", String(channelCoverage.active))
        .replace("{{signed}}", String(channelCoverage.signed)),
      icon: Waypoints,
      metric: t("agentInstancesChecklistChannelMetric").replace("{{count}}", String(channelCoverage.bound)),
      status: channelCoverage.bound ? t("agentInstancesChecklistPassed") : t("agentInstancesChecklistNeedsFix"),
      title: t("agentInstancesChecklistChannel"),
      tone: channelCoverage.bound ? (channelCoverage.unsigned ? "warning" : "ok") : "blocked",
    },
    {
      action: runtimeTarget ? () => onRunInstance(runtimeTarget) : onCreateInstance,
      detail: t("agentInstancesChecklistRuntimeDetail").replace("{{runnable}}", String(runnableInstances.length)),
      icon: CheckCircle2,
      metric: runtimeTarget
        ? t("agentInstancesChecklistRuntimeMetricReady")
        : t("agentInstancesChecklistRuntimeMetricEmpty"),
      status: runnableInstances.length ? t("agentInstancesChecklistPassed") : t("agentInstancesChecklistNeedsTest"),
      title: t("agentInstancesChecklistRuntime"),
      tone: runnableInstances.length ? "ok" : runtimeTarget ? "warning" : "blocked",
    },
    {
      action: onOpenPublished,
      detail: t("agentInstancesChecklistVisibilityDetail").replace("{{visible}}", String(visibleInstances.length)),
      icon: Eye,
      metric: t("agentInstancesChecklistVisibilityMetric").replace("{{count}}", String(activeInstances.length)),
      status: visibleInstances.length ? t("agentInstancesChecklistPassed") : t("agentInstancesChecklistNeedsFix"),
      title: t("agentInstancesChecklistVisibility"),
      tone: visibleInstances.length ? "ok" : activeInstances.length ? "warning" : "blocked",
    },
  ];

  const passed = checks.filter((check) => check.tone === "ok").length;

  return (
    <section className="agent-handoff-checklist" aria-label={t("agentInstancesChecklistTitle")}>
      <div className="agent-handoff-checklist-head">
        <span className="agent-handoff-checklist-icon">
          <ShieldCheck size={18} />
        </span>
        <div>
          <span>{t("agentInstancesChecklistEyebrow")}</span>
          <strong>{t("agentInstancesChecklistTitle")}</strong>
          <p>
            {t("agentInstancesChecklistDescription")
              .replace("{{passed}}", String(passed))
              .replace("{{total}}", String(checks.length))}
          </p>
        </div>
        <StatusBadge
          label={passed === checks.length ? t("agentInstancesChecklistReady") : t("agentInstancesChecklistNeedsReview")}
          status={passed === checks.length ? "ready" : "warning"}
        />
      </div>
      <div className="agent-handoff-checklist-grid">
        {checks.map((check) => {
          const Icon = check.icon;
          return (
            <button
              className={cx("agent-handoff-checklist-card", check.tone)}
              key={check.title}
              onClick={check.action}
              type="button"
            >
              <span className="agent-handoff-checklist-card-icon">
                <Icon size={17} />
              </span>
              <span className="agent-handoff-checklist-copy">
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
