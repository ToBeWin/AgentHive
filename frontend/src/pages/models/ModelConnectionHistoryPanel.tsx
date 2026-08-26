import { Activity, RefreshCw } from "lucide-react";
import { useMemo, useState } from "react";
import { ApiNotice, Button, cx, PageTabs, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { LLMConnectionTestHistoryItem } from "../../lib/api";

type ModelConnectionHistoryTab = "summary" | "history";

interface ModelConnectionHistoryPanelProps {
  historyError: string | null;
  historyList: LLMConnectionTestHistoryItem[];
  historyLoading: boolean;
  refetchHistory: () => void;
}

export function ModelConnectionHistoryPanel({
  historyError,
  historyList,
  historyLoading,
  refetchHistory,
}: ModelConnectionHistoryPanelProps) {
  const { t } = useLocale();
  const [activeTab, setActiveTab] = useState<ModelConnectionHistoryTab>("summary");
  const failureCount = historyList.filter((item) => !item.ok).length;
  const summary = useMemo(() => summarizeConnectionHistory(historyList), [historyList]);

  return (
    <section className="panel model-connection-history-panel">
      <div className="panel-title-row">
        <div>
          <h2>{t("modelsConnectionHistory")}</h2>
          <p>
            {historyList.length} {t("modelsRecentTests")} · {failureCount} {t("modelsFailedTests")}
          </p>
        </div>
        <Button onClick={refetchHistory}>
          <RefreshCw size={16} /> {t("modelsRefresh")}
        </Button>
      </div>
      {historyError && <ApiNotice title={t("modelsConnectionHistoryUnavailable")} message={historyError} />}
      {historyLoading && <p className="inline-note">{t("modelsLoadingConnectionHistory")}</p>}
      {!historyLoading && !historyList.length && <p className="inline-note">{t("modelsNoConnectionHistory")}</p>}
      {historyList.length > 0 && (
        <div className="nested-workspace model-connection-history-workspace">
          <PageTabs
            active={activeTab}
            onChange={setActiveTab}
            tabs={[
              {
                id: "summary",
                label: t("modelsConnectionSummaryTab"),
                description: t("modelsConnectionSummaryTabDesc"),
              },
              {
                id: "history",
                label: t("modelsConnectionHistoryTab"),
                description: t("modelsConnectionHistoryTabDesc"),
              },
            ]}
          />
          {activeTab === "summary" && <ConnectionHistorySummary summary={summary} />}
          {activeTab === "history" && (
            <div className="connection-history-list">
              {historyList.map((item) => (
                <ConnectionHistoryItem item={item} key={item.id} />
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function ConnectionHistorySummary({ summary }: { summary: ConnectionHistorySummaryModel }) {
  const { t } = useLocale();
  const latest = summary.latest;
  return (
    <div className="connection-summary-grid">
      <ConnectionSummaryMetric label={t("modelsConnectionSummaryRecent")} value={String(summary.total)} />
      <ConnectionSummaryMetric label={t("modelsConnectionSummaryAcceptance")} value={String(summary.acceptance)} />
      <ConnectionSummaryMetric
        label={t("modelsConnectionSummaryFailed")}
        value={String(summary.failed)}
        tone={summary.failed > 0 ? "error" : "ok"}
      />
      <ConnectionSummaryMetric label={t("modelsConnectionSummaryLive")} value={String(summary.live)} />
      <ConnectionSummaryMetric label={t("modelsConnectionSummaryTemporary")} value={String(summary.temporary)} />
      {latest && (
        <article className={cx("connection-summary-latest", latest.ok ? "ok" : "error")}>
          <div>
            <span>{t("modelsConnectionSummaryLatest")}</span>
            <strong>
              {latest.provider_key ?? t("modelsUnknownProvider")} · {latest.model_key ?? t("modelsNotSet")}
            </strong>
          </div>
          <StatusBadge
            label={latest.ok ? t("modelsConnectionHealthy") : t("modelsConnectionFailed")}
            status={latest.ok ? "active" : "error"}
          />
          <small>
            {formatDateTime(latest.checked_at)} · {latest.latency_ms ?? "-"}ms
            {latest.live_network_call ? ` · ${t("modelsLiveNetworkCall")}` : ""}
          </small>
          <p>
            {latest.ok
              ? t("modelsConnectionAccepted")
                  .replace("{{provider}}", latest.provider_key ?? t("modelsUnknownProvider"))
                  .replace("{{latency}}", String(latest.latency_ms ?? 0))
              : t("modelsProviderReadinessFailureDetail")}
          </p>
        </article>
      )}
    </div>
  );
}

function ConnectionSummaryMetric({
  label,
  tone = "neutral",
  value,
}: {
  label: string;
  tone?: "neutral" | "ok" | "error";
  value: string;
}) {
  return (
    <article className={cx("connection-summary-metric", tone)}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function ConnectionHistoryItem({ item }: { item: LLMConnectionTestHistoryItem }) {
  const { t } = useLocale();
  const routeReason = item.selected_route_reason ?? t("modelsNotSet");
  const fallbackText =
    item.fallback_attempt_count && item.fallback_attempt_count > 0
      ? `${item.fallback_attempt_count} ${t("modelsFallbacksUsed")}`
      : t("modelsNoFallbackUsed");
  const metaItems = [
    item.operation ? `${t("modelsOperation")}: ${formatOperationLabel(item.operation, t)}` : null,
    item.provider_type ? item.provider_type : null,
    item.configuration_source ? `${t("modelsConfigurationSource")}: ${item.configuration_source}` : null,
    item.live_network_call ? t("modelsLiveNetworkCall") : null,
    item.live_network_call === false ? t("modelsMockConnection") : null,
    item.status_code !== null ? `${t("modelsHttpStatus")} ${item.status_code}` : null,
    item.probe_path ? `${t("modelsProbePath")}: ${item.probe_path}` : null,
  ].filter((meta): meta is string => Boolean(meta));

  return (
    <article className={cx("connection-history-item", item.ok ? "ok" : "error")}>
      <span className="connection-history-icon">
        <Activity size={16} />
      </span>
      <div className="connection-history-body">
        <div className="connection-history-main">
          <strong>
            {item.provider_key ?? t("modelsUnknownProvider")} · {item.model_key ?? t("modelsNotSet")}
          </strong>
          <StatusBadge
            label={item.ok ? t("modelsConnectionHealthy") : t("modelsConnectionFailed")}
            status={item.ok ? "active" : "error"}
          />
        </div>
        <span>
          {formatDateTime(item.checked_at)} · {item.latency_ms ?? "-"}ms · {fallbackText}
        </span>
        <small>
          {routeReason}
          {item.temporary_api_key_provided || item.temporary_base_url_provided
            ? ` · ${t("modelsTemporaryCredential")}`
            : ""}
        </small>
        {metaItems.length > 0 && (
          <div className="connection-history-meta">
            {metaItems.map((meta) => (
              <span key={meta}>{meta}</span>
            ))}
          </div>
        )}
        <p>{item.ok ? t("modelsConnectionHealthy") : t("modelsProviderReadinessFailureDetail")}</p>
      </div>
    </article>
  );
}

function formatDateTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
  }).format(date);
}

interface ConnectionHistorySummaryModel {
  acceptance: number;
  failed: number;
  latest: LLMConnectionTestHistoryItem | null;
  live: number;
  temporary: number;
  total: number;
}

function summarizeConnectionHistory(historyList: LLMConnectionTestHistoryItem[]): ConnectionHistorySummaryModel {
  return {
    acceptance: historyList.filter((item) => item.operation === "deployment_acceptance_test").length,
    failed: historyList.filter((item) => !item.ok).length,
    latest: historyList[0] ?? null,
    live: historyList.filter((item) => item.live_network_call).length,
    temporary: historyList.filter((item) => item.temporary_api_key_provided || item.temporary_base_url_provided).length,
    total: historyList.length,
  };
}

function formatOperationLabel(operation: string, t: (key: string) => string) {
  if (operation === "deployment_acceptance_test") {
    return t("modelsOperationDeploymentAcceptance");
  }
  if (operation === "media_provider_live_probe") {
    return t("modelsOperationMediaLiveProbe");
  }
  if (operation === "media_provider_configuration_check") {
    return t("modelsOperationMediaConfigCheck");
  }
  return operation;
}
