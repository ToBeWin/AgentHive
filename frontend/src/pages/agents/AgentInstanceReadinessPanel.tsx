import { Bot, CheckCircle2, DatabaseZap, Route, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { AgentInstanceResponse, BudgetPolicyResponse, ChannelResponse } from "../../lib/api";
import { readinessReasonAdminAction, readinessReasonLabel, uniqueReadinessReasons } from "../../lib/readiness";
import { AgentHandoffChecklistPanel } from "./AgentHandoffChecklistPanel";
import { type AgentKnowledgeBaseOption, knowledgeBaseIdsFromConfig } from "./agentInstanceUtils";

interface AgentInstanceReadinessPanelProps {
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

export function AgentInstanceReadinessPanel({
  budgetPolicies,
  channels,
  instances,
  knowledgeBases,
  onOpenBudgets,
  onOpenChannels,
  onCreateInstance,
  onOpenPublished,
  onRunInstance,
}: AgentInstanceReadinessPanelProps) {
  const { t } = useLocale();
  const metrics = getAgentInstanceReadiness(instances, knowledgeBases, t);
  const reasonSummary = getReadinessReasonSummary(instances);
  const Icon = metrics.kind === "ready" ? CheckCircle2 : metrics.kind === "warning" ? TriangleAlert : Bot;

  return (
    <section className={cx("agent-instance-readiness-panel", metrics.kind)}>
      <div className="agent-instance-readiness-header">
        <span className="agent-instance-readiness-icon">
          <Icon size={18} />
        </span>
        <div>
          <h3>{t("agentInstancesReadinessTitle")}</h3>
          <p>{metrics.message}</p>
        </div>
        <StatusBadge label={metrics.label} status={metrics.status} />
      </div>
      <div className="agent-instance-readiness-grid">
        <ReadinessMetric icon={<Bot size={15} />} label={t("agentInstancesTotal")} value={String(metrics.total)} />
        <ReadinessMetric
          icon={<CheckCircle2 size={15} />}
          label={t("agentInstancesActive")}
          value={String(metrics.active)}
        />
        <ReadinessMetric
          icon={<DatabaseZap size={15} />}
          label={t("agentInstancesWithKnowledge")}
          value={String(metrics.withKnowledge)}
        />
        <ReadinessMetric
          icon={<Route size={15} />}
          label={t("agentInstancesWithRoute")}
          value={String(metrics.withRoute)}
        />
        <ReadinessMetric
          icon={<CheckCircle2 size={15} />}
          label={t("agentInstancesPublishReady")}
          value={String(metrics.publishReady)}
        />
        <ReadinessMetric
          icon={<Route size={15} />}
          label={t("agentInstancesModelAvailable")}
          value={String(metrics.modelAvailable)}
        />
      </div>
      {metrics.gaps.length > 0 && (
        <div className="agent-instance-readiness-gaps">
          {metrics.gaps.map((gap) => (
            <span key={gap}>{gap}</span>
          ))}
        </div>
      )}
      {reasonSummary.length > 0 && (
        <section className="agent-instance-readiness-actions" aria-label={t("agentInstancesReadinessActionPlan")}>
          <div>
            <strong>{t("agentInstancesReadinessActionPlan")}</strong>
            <small>{t("agentInstancesReadinessActionPlanDesc")}</small>
          </div>
          <div className="agent-instance-readiness-action-grid">
            {reasonSummary.map((item) => (
              <article key={item.reason}>
                <span>{t("agentInstancesReadinessAffected").replace("{{count}}", String(item.count))}</span>
                <strong>{readinessReasonLabel(item.reason, t)}</strong>
                <p>{readinessReasonAdminAction(item.reason, t)}</p>
              </article>
            ))}
          </div>
        </section>
      )}
      <AgentHandoffChecklistPanel
        budgetPolicies={budgetPolicies}
        channels={channels}
        instances={instances}
        knowledgeBases={knowledgeBases}
        onOpenBudgets={onOpenBudgets}
        onOpenChannels={onOpenChannels}
        onCreateInstance={onCreateInstance}
        onOpenPublished={onOpenPublished}
        onRunInstance={onRunInstance}
      />
    </section>
  );
}

function getReadinessReasonSummary(instances: AgentInstanceResponse[]) {
  const counts = new Map<string, number>();
  for (const instance of instances) {
    for (const reason of uniqueReadinessReasons(instance.readiness_reasons ?? [])) {
      counts.set(reason, (counts.get(reason) ?? 0) + 1);
    }
  }
  return Array.from(counts.entries())
    .map(([reason, count]) => ({ reason, count }))
    .sort((a, b) => b.count - a.count || a.reason.localeCompare(b.reason));
}

function ReadinessMetric({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="agent-instance-readiness-metric">
      <span>
        {icon}
        {label}
      </span>
      <strong>{value}</strong>
    </div>
  );
}

function getAgentInstanceReadiness(
  instances: AgentInstanceResponse[],
  knowledgeBases: AgentKnowledgeBaseOption[],
  t: (key: string) => string,
) {
  const total = instances.length;
  const active = instances.filter((instance) => instance.status === "active").length;
  const withKnowledge = instances.filter((instance) => knowledgeBaseIdsFromConfig(instance.config).length > 0).length;
  const withRoute = instances.filter((instance) => Boolean(instance.model_routing_key || instance.model_key)).length;
  const publishReady = instances.filter((instance) =>
    instance.runnable === undefined ? instance.status === "active" : instance.status === "active" && instance.runnable,
  ).length;
  const modelAvailable = instances.filter((instance) =>
    instance.model_available === undefined
      ? Boolean(instance.model_routing_key || instance.model_key)
      : instance.model_available,
  ).length;
  const modelUnavailable = instances.filter((instance) =>
    (instance.readiness_reasons ?? []).some((reason) =>
      ["model_route_unavailable", "model_unavailable"].includes(reason),
    ),
  ).length;
  const knownKnowledgeIds = new Set(knowledgeBases.map((base) => base.id));
  const missingKnowledgeBindings = instances.filter((instance) =>
    knowledgeBaseIdsFromConfig(instance.config).some((id) => !knownKnowledgeIds.has(id)),
  ).length;
  const gaps: string[] = [];

  if (total === 0) {
    return {
      active,
      gaps,
      kind: "empty",
      label: t("agentInstancesReadinessNotReady"),
      message: t("agentInstancesReadinessCreateFirst"),
      status: "inactive",
      total,
      withKnowledge,
      withRoute,
      publishReady,
      modelAvailable,
    };
  }
  if (active === 0) {
    gaps.push(t("agentInstancesGapNoActive"));
  }
  if (withKnowledge === 0) {
    gaps.push(t("agentInstancesGapNoKnowledge"));
  }
  if (withRoute === 0) {
    gaps.push(t("agentInstancesGapNoRoute"));
  }
  if (modelUnavailable > 0) {
    gaps.push(t("agentInstancesGapModelUnavailable").replace("{{count}}", String(modelUnavailable)));
  }
  if (missingKnowledgeBindings > 0) {
    gaps.push(t("agentInstancesGapStaleKnowledge").replace("{{count}}", String(missingKnowledgeBindings)));
  }

  if (active > 0 && publishReady === active && withKnowledge > 0 && gaps.length === 0) {
    return {
      active,
      gaps,
      kind: "ready",
      label: t("agentInstancesReadinessReady"),
      message: t("agentInstancesReadinessReadyMessage"),
      status: "ready",
      total,
      withKnowledge,
      withRoute,
      publishReady,
      modelAvailable,
    };
  }

  return {
    active,
    gaps,
    kind: "warning",
    label: t("agentInstancesReadinessNeedsReview"),
    message: t("agentInstancesReadinessReviewMessage"),
    status: "warning",
    total,
    withKnowledge,
    withRoute,
    publishReady,
    modelAvailable,
  };
}
