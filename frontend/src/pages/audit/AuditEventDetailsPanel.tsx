import { Copy, X } from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { Button, PageTabs, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { AuditLogItem } from "../../lib/api";
import { formatDateTime } from "../../lib/formatters";
import { auditRuntimeSummary, auditStatusLabel, compactResource } from "./auditUtils";

type AuditDetailsTab = "summary" | "context" | "raw";

export function AuditEventDetailsPanel({ event, onClose }: { event: AuditLogItem | null; onClose: () => void }) {
  const { locale, t } = useLocale();
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<AuditDetailsTab>("summary");
  const eventJson = useMemo(() => (event ? JSON.stringify(event, null, 2) : ""), [event]);
  const runtimeSummary = useMemo(() => (event ? auditRuntimeSummary(event.details) : null), [event]);
  const canCopy = typeof navigator !== "undefined" && Boolean(navigator.clipboard);

  const copyEventJson = async () => {
    if (!eventJson || !canCopy) {
      return;
    }
    await navigator.clipboard.writeText(eventJson);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  if (!event) {
    return (
      <section className="panel audit-details-panel audit-details-empty">
        <h2>{t("auditEventDetails")}</h2>
        <p>{t("auditSelectEventPrompt")}</p>
      </section>
    );
  }

  return (
    <section className="panel audit-details-panel">
      <div className="panel-title">
        <h2>{t("auditEventDetails")}</h2>
        <div className="table-action-row">
          <Button onClick={copyEventJson} disabled={!canCopy}>
            <Copy size={15} /> {copied ? t("auditCopied") : t("auditCopyJson")}
          </Button>
          <Button onClick={onClose}>
            <X size={15} /> {t("auditCloseDetails")}
          </Button>
        </div>
      </div>
      <PageTabs
        active={activeTab}
        onChange={setActiveTab}
        tabs={[
          { id: "summary", label: t("auditDetailsTabSummary"), description: t("auditDetailsTabSummaryDesc") },
          { id: "context", label: t("auditDetailsTabContext"), description: t("auditDetailsTabContextDesc") },
          { id: "raw", label: t("auditDetailsTabRaw"), description: t("auditDetailsTabRawDesc") },
        ]}
      />
      {activeTab === "summary" && (
        <>
          <div className="audit-details-grid">
            <AuditDetail label={t("auditEventId")} value={event.id} />
            <AuditDetail label={t("auditTimestamp")} value={formatDateTime(event.created_at, locale)} />
            <AuditDetail label={t("auditStatus")} value={<StatusBadge status={auditStatusLabel(event.status, t)} />} />
            <AuditDetail label={t("auditActor")} value={event.actor_id ?? event.actor_type} />
            <AuditDetail label={t("auditActionType")} value={event.action} />
            <AuditDetail label={t("auditResource")} value={compactResource(event, t("auditSystemResource"))} />
          </div>
          {runtimeSummary && (
            <section className="audit-runtime-evidence">
              <div>
                <span>{t("auditRuntimeEvidence")}</span>
                <strong>{runtimeSummaryLabel(runtimeSummary.status, t)}</strong>
                <small>
                  {t("auditRuntimeEvidenceDetail")
                    .replace("{{execution}}", runtimeSummary.execution)
                    .replace("{{mode}}", runtimeSummary.adapterMode)
                    .replace("{{model}}", runtimePair(runtimeSummary.providerKey, runtimeSummary.modelKey))
                    .replace("{{deployment}}", runtimeSummary.deploymentId)
                    .replace("{{fallbacks}}", runtimeSummary.fallbackAttemptCount)
                    .replace("{{gateway}}", runtimeSummary.gatewayCalled ? t("commonYes") : t("commonNo"))}
                </small>
                {runtimeSummary.routingKey !== "-" && (
                  <small>{t("auditRuntimeRoute").replace("{{route}}", runtimeSummary.routingKey)}</small>
                )}
              </div>
              {runtimeSummary.routeAttempts.length ? (
                <div className="audit-route-attempt-list">
                  {runtimeSummary.routeAttempts.map((attempt) => (
                    <article key={`${attempt.deploymentId}-${attempt.attempt}`}>
                      <strong>
                        #{attempt.attempt} · {attempt.providerKey}
                      </strong>
                      <small>
                        {attempt.modelKey} · {attempt.routingKey} · {attempt.status}
                      </small>
                      {attempt.errorCode !== "-" && <small>{attempt.errorCode}</small>}
                    </article>
                  ))}
                </div>
              ) : null}
            </section>
          )}
        </>
      )}
      {activeTab === "context" && (
        <>
          <div className="audit-details-grid">
            <AuditDetail label={t("auditRequestId")} value={event.request_id ?? "-"} />
            <AuditDetail label={t("auditIpAddress")} value={event.ip_address ?? "-"} />
          </div>
          <div className="audit-user-agent">
            <span>{t("auditUserAgent")}</span>
            <code>{event.user_agent ?? "-"}</code>
          </div>
        </>
      )}
      {activeTab === "raw" && <pre className="audit-json-viewer">{eventJson}</pre>}
    </section>
  );
}

function AuditDetail({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="audit-detail-item">
      <span>{label}</span>
      <div>{value}</div>
    </div>
  );
}

function runtimeSummaryLabel(status: string, t: (key: string) => string) {
  if (status === "real_model_call") {
    return t("auditRuntimeRealModelCall");
  }
  if (status === "mock_model_call") {
    return t("auditRuntimeMockModelCall");
  }
  if (status === "media_generation_task") {
    return t("auditRuntimeMediaGenerationTask");
  }
  if (status === "local_runtime") {
    return t("auditRuntimeLocalRuntime");
  }
  return t("auditRuntimeUnknown");
}

function runtimePair(providerKey: string, modelKey: string) {
  if (providerKey === "-" && modelKey === "-") {
    return "-";
  }
  if (providerKey === "-") {
    return modelKey;
  }
  if (modelKey === "-") {
    return providerKey;
  }
  return `${providerKey}/${modelKey}`;
}
