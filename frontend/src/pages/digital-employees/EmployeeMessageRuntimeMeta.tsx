import { useLocale } from "../../i18n-context";
import type { ChatMessageResponse } from "../../lib/api";
import { type ChatRunDetails, latestAssistantRunDetails } from "../chat/chatRunDetails";
import { formatRuntimeCost, numericValue, runtimePair } from "./employeeTaskRuntimeUtils";

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function asRecordArray(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object");
}

export function EmployeeMessageRuntimeMeta({ message }: { message: ChatMessageResponse }) {
  const { t } = useLocale();
  const details = latestAssistantRunDetails([message]);
  if (!hasRuntimeEvidence(details, message)) {
    return null;
  }

  return (
    <dl className="employee-message-runtime" aria-label={t("digitalEmployeesRuntimeEvidence")}>
      <div>
        <dt>{t("digitalEmployeesTaskRoute")}</dt>
        <dd>
          <strong>{runtimePair(details.providerKey, details.modelKey)}</strong>
          <small>{runtimeModeLabel(details, t)}</small>
        </dd>
      </div>
      <div>
        <dt>{t("digitalEmployeesTaskTokens")}</dt>
        <dd>
          <strong>{details.runtimeTotalTokens}</strong>
          <small>
            {t("digitalEmployeesRuntimeTokenBreakdown")
              .replace("{{input}}", details.runtimeInputTokens)
              .replace("{{output}}", details.runtimeOutputTokens)}
          </small>
        </dd>
      </div>
      <div>
        <dt>{t("digitalEmployeesRuntimeCost")}</dt>
        <dd>
          <strong>{formatRuntimeCost(details.runtimeCostUsd)}</strong>
          <small>{details.budgetGuardStatus !== "-" ? details.budgetGuardStatus : details.budgetEvent}</small>
        </dd>
      </div>
      <div>
        <dt>{t("digitalEmployeesRuntimeRequest")}</dt>
        <dd>
          <strong>{details.requestId}</strong>
          <small>
            {details.runtimeFallbackAttempts !== "-"
              ? t("digitalEmployeesRuntimeFallbacks").replace("{{count}}", details.runtimeFallbackAttempts)
              : "-"}
          </small>
        </dd>
      </div>
      {orchestrationTrace(message).length > 0 ? (
        <div className="employee-message-runtime-trace">
          <dt>{t("digitalEmployeesOrchestrationTrace")}</dt>
          <dd>
            <ol>
              {orchestrationTrace(message).map((step) => (
                <li key={`${step.node}-${step.detail}`}>
                  <strong>{step.node}</strong>
                  <span>{step.detail}</span>
                </li>
              ))}
            </ol>
            {(() => {
              const confidence = orchestrationConfidence(message);
              return confidence ? (
                <small>{t("digitalEmployeesOrchestrationConfidence").replace("{{value}}", confidence)}</small>
              ) : null;
            })()}
          </dd>
        </div>
      ) : null}
    </dl>
  );
}

function hasRuntimeEvidence(details: ChatRunDetails, message: ChatMessageResponse) {
  return (
    details.runtimeGatewayCalled ||
    details.runtimeSummaryStatus !== "-" ||
    details.providerKey !== "-" ||
    details.modelKey !== "-" ||
    details.requestId !== "-" ||
    numericValue(details.runtimeTotalTokens) > 0 ||
    numericValue(details.runtimeCostUsd) > 0 ||
    orchestrationTrace(message).length > 0
  );
}

function orchestrationTrace(message: ChatMessageResponse) {
  const metadata = asRecord(message.metadata);
  const runtime = asRecord(metadata?.runtime_evidence);
  return asRecordArray(runtime?.langgraph_trace)
    .map((step) => ({
      node: String(step.node ?? ""),
      detail: String(step.detail ?? ""),
    }))
    .filter((step) => step.node && step.detail);
}

function orchestrationConfidence(message: ChatMessageResponse) {
  const metadata = asRecord(message.metadata);
  const runtime = asRecord(metadata?.runtime_evidence);
  const value = runtime?.langgraph_confidence;
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const numeric = Number(value);
  if (Number.isNaN(numeric)) {
    return String(value);
  }
  return numeric.toFixed(2);
}

function runtimeModeLabel(details: ChatRunDetails, t: (key: string) => string) {
  if (details.runtimeSummaryStatus === "real_model_call") {
    return t("digitalEmployeesRuntimeRealModelCall");
  }
  if (details.runtimeSummaryStatus === "mock_model_call") {
    return t("digitalEmployeesRuntimeMockModelCall");
  }
  if (details.runtimeSummaryStatus === "media_generation_task") {
    return t("digitalEmployeesRuntimeMediaGateway");
  }
  if (details.runtimeSummaryStatus === "local_runtime") {
    return t("digitalEmployeesRuntimeLocalRuntime");
  }
  if (details.runtimeGatewayCalled) {
    return t("digitalEmployeesRuntimeGateway");
  }
  if (details.runtimeLocalResponse !== "-") {
    return details.runtimeLocalResponse;
  }
  return details.runtimeSelectedRouteReason;
}
