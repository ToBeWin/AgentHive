import { BadgeCheck, DatabaseZap, Gauge, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { cx, PageTabs, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { ChatMessageResponse } from "../../lib/api";
import { formatCurrency } from "../../lib/formatters";
import { chatConfidenceLabelKey, latestAssistantRunDetails } from "./chatRunDetails";

type RunDetailsTab = "summary" | "governance" | "knowledge" | "sources";

export function ChatRunDetailsPanel({ messages }: { messages: ChatMessageResponse[] }) {
  const { t } = useLocale();
  const details = useMemo(() => latestAssistantRunDetails(messages), [messages]);
  const [activeTab, setActiveTab] = useState<RunDetailsTab>("summary");

  return (
    <section className="panel chat-run-details-panel">
      <div className="panel-title">
        <h2>
          {t("chatRunDetails")} <span>{t("chatRunDetailsAlt")}</span>
        </h2>
        {details.message && <StatusBadge status={details.execution} label={executionLabel(details.execution, t)} />}
      </div>
      {!details.message ? (
        <p className="muted">{t("chatRunDetailsEmpty")}</p>
      ) : (
        <>
          <PageTabs
            active={activeTab}
            onChange={setActiveTab}
            tabs={[
              { id: "summary", label: t("chatRunSummaryTab"), description: t("chatRunSummaryTabDesc") },
              { id: "governance", label: t("chatRunGovernanceTab"), description: t("chatRunGovernanceTabDesc") },
              { id: "knowledge", label: t("chatRunKnowledgeTab"), description: t("chatRunKnowledgeTabDesc") },
              { id: "sources", label: t("chatRunSourcesTab"), description: t("chatRunSourcesTabDesc") },
            ]}
          />

          {activeTab === "summary" && (
            <>
              <div className="chat-run-grid">
                <RunMetric
                  detail={details.providerKey}
                  icon={<Gauge size={17} />}
                  label={t("chatRunModel")}
                  value={details.modelKey}
                />
                <RunMetric
                  detail={details.requestId}
                  icon={<ShieldCheck size={17} />}
                  label={t("chatRunRequest")}
                  value={details.runtimeTotalTokens}
                />
                <RunMetric
                  detail={formatCurrency(details.runtimeCostUsd)}
                  icon={<BadgeCheck size={17} />}
                  label={t("chatRunRuntimeCost")}
                  value={details.runtimeGatewayCalled ? t("chatRunGatewayCalled") : t("chatRunGatewaySkipped")}
                />
                <RunMetric
                  detail={details.runtimeSelectedRouteReason}
                  icon={<DatabaseZap size={17} />}
                  label={t("chatRunRouteAttempts")}
                  value={details.runtimeRouteAttempts}
                />
              </div>
              <div className="chat-run-section">
                <span>{t("chatRunRuntimeEvidence")}</span>
                <strong>
                  {t("chatRunInputOutputTokens")
                    .replace("{{input}}", details.runtimeInputTokens)
                    .replace("{{output}}", details.runtimeOutputTokens)}
                </strong>
                <p>
                  {t("chatRunFallbackDetail")
                    .replace("{{count}}", details.runtimeFallbackAttempts)
                    .replace("{{mock}}", details.runtimeMockAdapter ? t("commonYes") : t("commonNo"))}
                </p>
              </div>
              {!details.runtimeGatewayCalled && details.runtimeLocalResponse !== "-" && (
                <div className="chat-run-section local-decision">
                  <span>{t("chatRunLocalDecision")}</span>
                  <strong>{details.runtimeLocalResponse}</strong>
                  <p>{details.runtimeSelectedRouteReason}</p>
                </div>
              )}
              {hasRuntimeFailure(details) && (
                <div className="chat-run-section route-failure">
                  <span>{t("chatRunRouteFailure")}</span>
                  <strong>{runtimeFailureTitle(details, t)}</strong>
                  <p>
                    {t("chatRunRouteFailureDetail")
                      .replace("{{operation}}", details.runtimeFailureOperation)
                      .replace("{{status}}", details.runtimeHttpStatus)
                      .replace("{{candidates}}", details.runtimeFailureCandidateCount)
                      .replace("{{missing}}", details.runtimeMissingProviderKeys)}
                  </p>
                  {details.runtimeFailureDetail !== "-" && <small>{details.runtimeFailureDetail}</small>}
                </div>
              )}
              {details.routeAttempts.length ? (
                <div className="chat-route-attempts">
                  <span>{t("chatRunRouteTimeline")}</span>
                  {details.routeAttempts.map((attempt) => (
                    <article key={`${attempt.id}-${attempt.attempt}`}>
                      <strong>
                        #{attempt.attempt} · {attempt.providerKey}
                      </strong>
                      <small>
                        {attempt.modelKey} · {attempt.status}
                      </small>
                      <small>
                        {t("chatRunRoutingKey")}: {attempt.routingKey} · {t("chatRunDeploymentId")}:{" "}
                        {attempt.deploymentId}
                      </small>
                    </article>
                  ))}
                </div>
              ) : null}
              <div className="chat-run-section">
                <span>{t("chatRunAgentInstance")}</span>
                <strong>{details.agentInstanceName}</strong>
                <p>{details.agentInstanceDetail}</p>
              </div>
            </>
          )}

          {activeTab === "governance" && (
            <>
              <div className="chat-run-section">
                <span>{t("chatRunLicenseEvidence")}</span>
                <strong>{details.licenseGate}</strong>
                <p>{details.licenseReason}</p>
              </div>
              <div className="chat-run-section">
                <span>{t("chatRunBudgetEvidence")}</span>
                <strong>
                  {details.budgetPolicyName} · {details.budgetGuardStatus}
                </strong>
                <p>
                  {details.budgetReason}{" "}
                  {t("chatRunBudgetLedgerDetail")
                    .replace("{{event}}", details.budgetEvent)
                    .replace("{{cost}}", formatCurrency(details.budgetCost))
                    .replace("{{reservation}}", details.budgetReservationId)}
                </p>
                {details.budgetFallbackRequestId !== "-" && (
                  <small className="row-subtitle">
                    {t("chatRunBudgetFallback").replace("{{request}}", details.budgetFallbackRequestId)}
                  </small>
                )}
              </div>
            </>
          )}

          {activeTab === "knowledge" && (
            <>
              <div className={cx("chat-run-section", details.knowledgeRequiresReview && "needs-review")}>
                <span>{t("chatRunKnowledgePlan")}</span>
                <strong>
                  {details.knowledgeEnabled ? t("chatRunKnowledgeEnabled") : t("chatRunKnowledgeDisabled")}
                </strong>
                <p>
                  {t("chatRunKnowledgePlanDetail")
                    .replace("{{topK}}", details.knowledgeTopK)
                    .replace("{{count}}", details.knowledgeSourceCount)}{" "}
                  · {t(chatConfidenceLabelKey(details.knowledgeConfidence))} ·{" "}
                  {t("chatRunMaxScore").replace("{{score}}", details.knowledgeMaxScore)}
                </p>
                {details.knowledgeRequiresReview && (
                  <small className="message-trace-review">
                    {t("chatRunHumanReviewRequired")} · {details.knowledgeReviewReason}
                  </small>
                )}
              </div>
              {details.perBase.length ? (
                <div className="chat-run-kb-list">
                  {details.perBase.map((item) => (
                    <article key={`${item.id}-${item.engine}`}>
                      <strong>{item.name}</strong>
                      <span>
                        {item.visibility} · {item.engine} ·{" "}
                        {t("chatRunSourcesCount").replace("{{count}}", item.sourceCount)} · {item.elapsedMs}ms
                      </span>
                    </article>
                  ))}
                </div>
              ) : null}
            </>
          )}

          {activeTab === "sources" &&
            (details.sources.length ? (
              <div className="chat-source-list">
                <span>{t("chatRunSources")}</span>
                {details.sources.map((source) => (
                  <article key={source.id}>
                    <div>
                      <strong>{source.sourceName}</strong>
                      <small>
                        {source.knowledgeBaseName} · {t("chatRunScore")} {source.score}
                      </small>
                    </div>
                    {source.text !== "-" && <p>{source.text}</p>}
                  </article>
                ))}
              </div>
            ) : (
              <p className="muted">{t("chatRunNoSources")}</p>
            ))}
        </>
      )}
    </section>
  );
}

function RunMetric({ detail, icon, label, value }: { detail: string; icon: ReactNode; label: string; value: string }) {
  return (
    <div>
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function hasRuntimeFailure(details: ReturnType<typeof latestAssistantRunDetails>) {
  return (
    details.runtimeErrorCode !== "-" || details.runtimeHttpStatus !== "-" || details.runtimeMissingProviderKeys !== "-"
  );
}

function runtimeFailureTitle(details: ReturnType<typeof latestAssistantRunDetails>, t: (key: string) => string) {
  if (details.runtimeErrorMessage !== "-") {
    return `${details.runtimeErrorCode} · ${details.runtimeErrorMessage}`;
  }
  if (details.runtimeErrorCode !== "-") {
    return details.runtimeErrorCode;
  }
  return t("chatRunRouteFailureUnknown");
}

function executionLabel(execution: string, t: (key: string) => string) {
  if (execution === "agent_runtime") {
    return t("chatRunAgentRuntime");
  }
  if (execution === "streaming") {
    return t("chatRunStreaming");
  }
  if (execution === "local_response") {
    return t("chatRunLocalResponse");
  }
  if (execution === "knowledge_guardrail") {
    return t("chatRunKnowledgeGuardrail");
  }
  return execution;
}
