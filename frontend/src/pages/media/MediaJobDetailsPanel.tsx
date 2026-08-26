import { Download, FileText, Image, Video } from "lucide-react";
import { useEffect, useState } from "react";
import { Button, PageTabs, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import { type MediaGenerationJobEvent, type MediaGenerationJobResponse, mediaApi } from "../../lib/api";
import { downloadBlobFile } from "../../lib/download";
import { formatCurrency } from "../../lib/formatters";
import { MediaGovernanceSummaryPanel } from "./MediaGovernanceSummaryPanel";
import { formatDateTime, kindLabelKey, modeLabelKey, safeJson, shortId, statusLabelKey } from "./mediaUtils";

type MediaJobDetailsTab = "summary" | "assets" | "governance" | "execution" | "raw";

export function MediaJobDetailsPanel({
  canInspectExecution,
  events,
  eventsError,
  eventsLoading,
  job,
}: {
  canInspectExecution: boolean;
  events: MediaGenerationJobEvent[];
  eventsError: string | null;
  eventsLoading: boolean;
  job: MediaGenerationJobResponse | null;
}) {
  const { t } = useLocale();
  const [downloadingIndex, setDownloadingIndex] = useState<number | null>(null);
  const [downloadError, setDownloadError] = useState("");
  const [activeTab, setActiveTab] = useState<MediaJobDetailsTab>("summary");
  useEffect(() => {
    if (!canInspectExecution && (activeTab === "governance" || activeTab === "execution" || activeTab === "raw")) {
      setActiveTab("summary");
    }
  }, [activeTab, canInspectExecution]);
  if (!job) {
    return (
      <section className="panel media-details-panel empty">
        <FileText size={24} />
        <h2>{canInspectExecution ? t("mediaDetailsTitle") : t("mediaDetailsEmployeeTitle")}</h2>
        <p>{canInspectExecution ? t("mediaDetailsEmpty") : t("mediaDetailsEmployeeEmpty")}</p>
      </section>
    );
  }
  const downloadableOutputs = job.outputs
    .map((output, index) => ({ output, index }))
    .filter(({ output }) => typeof output.bucket === "string" && typeof output.object_key === "string");
  const estimatedCost =
    typeof job.metadata.estimated_cost_usd === "string" || typeof job.metadata.estimated_cost_usd === "number"
      ? formatCurrency(String(job.metadata.estimated_cost_usd))
      : "-";
  const downloadOutput = async (index: number) => {
    setDownloadingIndex(index);
    setDownloadError("");
    try {
      const response = await mediaApi.downloadGenerationOutput(job.id, index);
      downloadBlobFile(response.blob, response.filename ?? `agenthive-media-output-${index + 1}`);
    } catch {
      setDownloadError(t("mediaOutputDownloadFailed"));
    } finally {
      setDownloadingIndex(null);
    }
  };
  return (
    <section className="panel media-details-panel">
      <div className="panel-title-row">
        <div>
          <h2>{canInspectExecution ? t("mediaDetailsTitle") : t("mediaDetailsEmployeeTitle")}</h2>
          <p>
            {shortId(job.id)} · {formatDateTime(job.updated_at)}
          </p>
        </div>
        <StatusBadge label={t(statusLabelKey(job.status))} status={job.status} />
      </div>
      <div className="nested-workspace media-detail-workspace">
        <PageTabs
          active={activeTab}
          onChange={setActiveTab}
          tabs={[
            { id: "summary", label: t("mediaDetailsTabSummary"), description: t("mediaDetailsTabSummaryDesc") },
            { id: "assets", label: t("mediaDetailsTabAssets"), description: t("mediaDetailsTabAssetsDesc") },
            ...(canInspectExecution
              ? [
                  {
                    id: "governance" as const,
                    label: t("mediaDetailsTabGovernance"),
                    description: t("mediaDetailsTabGovernanceDesc"),
                  },
                  {
                    id: "execution" as const,
                    label: t("mediaDetailsTabExecution"),
                    description: t("mediaDetailsTabExecutionDesc"),
                  },
                  { id: "raw" as const, label: t("mediaDetailsTabRaw"), description: t("mediaDetailsTabRawDesc") },
                ]
              : []),
          ]}
        />
        {activeTab === "summary" && (
          <div className="media-detail-stack">
            <div className="media-job-summary-grid">
              <SummaryCard label={t("mediaKind")} value={t(kindLabelKey(job.kind))} />
              <SummaryCard label={t("mediaMode")} value={t(modeLabelKey(job.mode))} />
              <SummaryCard label={t("mediaEstimatedCost")} value={estimatedCost} />
              <SummaryCard label={t("mediaOutputs")} value={String(job.outputs.length)} />
            </div>
            <PromptBlock prompt={job.prompt} title={t("mediaPrompt")} />
            {job.negative_prompt && <PromptBlock prompt={job.negative_prompt} title={t("mediaNegativePrompt")} />}
            {job.error_message && <DetailBlock title={t("mediaError")} value={job.error_message} tone="error" />}
            <div className="media-job-facts">
              <Fact label={t("mediaCreated")} value={formatDateTime(job.created_at)} />
              <Fact label={t("mediaCompletedAt")} value={formatDateTime(job.completed_at)} />
            </div>
          </div>
        )}
        {activeTab === "assets" && (
          <div className="media-detail-stack">
            {downloadableOutputs.length > 0 && (
              <div className="media-output-actions">
                {downloadableOutputs.map(({ index }) => (
                  <Button key={index} onClick={() => void downloadOutput(index)} disabled={downloadingIndex === index}>
                    <Download size={15} /> {t("mediaDownloadOutput")} {index + 1}
                  </Button>
                ))}
              </div>
            )}
            {downloadError && <p className="field-help error">{downloadError}</p>}
            <AssetList
              assets={job.outputs}
              emptyText={t("mediaNoOutputs")}
              kind={job.kind}
              revealTechnicalDetails={canInspectExecution}
              title={t("mediaGeneratedAssets")}
            />
            <AssetList
              assets={job.reference_assets}
              emptyText={t("mediaNoReferenceAssets")}
              kind="reference"
              revealTechnicalDetails={canInspectExecution}
              title={t("mediaReferenceAssets")}
            />
          </div>
        )}
        {activeTab === "governance" && canInspectExecution && (
          <div className="media-detail-stack">
            <div className="media-job-summary-grid">
              <SummaryCard label={t("mediaProvider")} value={job.provider_key} />
              <SummaryCard label={t("mediaModel")} value={job.model_key} />
              <SummaryCard label={t("mediaRoutingKey")} value={job.routing_key} />
              <SummaryCard label={t("mediaEstimatedCost")} value={estimatedCost} />
            </div>
            <MediaGovernanceSummaryPanel job={job} />
            <div className="media-job-facts">
              <Fact label={t("mediaStartedAt")} value={formatDateTime(job.started_at)} />
              <Fact label={t("mediaCompletedAt")} value={formatDateTime(job.completed_at)} />
              <Fact label={t("mediaExternalJobId")} value={job.external_job_id ?? "-"} />
              <Fact label={t("mediaRequestId")} value={job.request_id ?? "-"} />
            </div>
          </div>
        )}
        {activeTab === "execution" && (
          <div className="media-detail-stack">
            <MediaExecutionEvidence events={events} job={job} />
            <TimelineBlock events={events} error={eventsError} loading={eventsLoading} />
            <StorageSummary storage={job.output_storage} />
          </div>
        )}
        {activeTab === "raw" && (
          <div className="media-detail-stack">
            <DetailBlock title={t("mediaRequestParameters")} value={safeJson(job.request_parameters)} />
            <DetailBlock title={t("mediaParameters")} value={safeJson(job.normalized_parameters)} />
            <DetailBlock title={t("mediaStorage")} value={safeJson(job.output_storage)} />
            <DetailBlock title={t("mediaOutputs")} value={safeJson(job.outputs)} />
            <DetailBlock title={t("mediaReferenceAssets")} value={safeJson(job.reference_assets)} />
            <DetailBlock title={t("mediaMetadata")} value={safeJson(job.metadata)} />
          </div>
        )}
      </div>
    </section>
  );
}

function SummaryCard({ label, value }: { label: string; value: string }) {
  return (
    <article className="media-summary-card">
      <span>{label}</span>
      <strong>{value || "-"}</strong>
    </article>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value || "-"}</strong>
    </div>
  );
}

function PromptBlock({ prompt, title }: { prompt: string; title: string }) {
  return (
    <article className="media-prompt-block">
      <strong>{title}</strong>
      <p>{prompt}</p>
    </article>
  );
}

function AssetList({
  assets,
  emptyText,
  kind,
  revealTechnicalDetails,
  title,
}: {
  assets: Record<string, unknown>[];
  emptyText: string;
  kind: "image" | "video" | "reference";
  revealTechnicalDetails: boolean;
  title: string;
}) {
  const { t } = useLocale();
  return (
    <article className="media-assets-block">
      <div className="media-assets-heading">
        <strong>{title}</strong>
        <span>{assets.length}</span>
      </div>
      {assets.length ? (
        <div className="media-asset-list">
          {assets.map((asset, index) => (
            <div className="media-asset-card" key={assetKey(asset, title)}>
              <div className="media-asset-icon">
                {kind === "video" || asset.kind === "video" ? <Video size={18} /> : <Image size={18} />}
              </div>
              <div>
                <strong>{assetTitle(asset, index, t)}</strong>
                <p>{assetSubtitle(asset, kind, revealTechnicalDetails, t)}</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="field-help">{emptyText}</p>
      )}
    </article>
  );
}

function TimelineBlock({
  error,
  events,
  loading,
}: {
  error: string | null;
  events: MediaGenerationJobEvent[];
  loading: boolean;
}) {
  const { t } = useLocale();
  return (
    <article className="media-timeline-block">
      <div className="media-timeline-heading">
        <strong>{t("mediaTimeline")}</strong>
        {loading && <span>{t("mediaTimelineLoading")}</span>}
      </div>
      {error && <p className="field-help error">{error}</p>}
      {!loading && !error && !events.length && <p className="field-help">{t("mediaTimelineEmpty")}</p>}
      {events.length > 0 && (
        <ol className="media-timeline-list">
          {events.map((event) => (
            <li key={event.id}>
              <span className="media-timeline-dot" />
              <div>
                <strong>{eventActionLabel(event.action, t)}</strong>
                <p>
                  {formatDateTime(event.created_at)} · {event.status}
                  {event.request_id ? ` · ${event.request_id}` : ""}
                </p>
                <details className="media-event-details">
                  <summary>{t("mediaEventDetails")}</summary>
                  <pre>{safeJson(event.details)}</pre>
                </details>
              </div>
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}

function MediaExecutionEvidence({
  events,
  job,
}: {
  events: MediaGenerationJobEvent[];
  job: MediaGenerationJobResponse;
}) {
  const { t } = useLocale();
  const latestEvidenceEvent = latestMediaEvidenceEvent(events);
  const details = latestEvidenceEvent?.details ?? {};
  const outputSummary = objectValue(details.output_summary);
  const archiveSummary = objectValue(details.output_archive);
  const reservation = objectValue(details.budget_reservation) || objectValue(job.metadata.budget_reservation);
  const budgetEvent = stringValue(details.budget_event) || t("mediaExecutionBudgetReserved");
  const budgetReason = stringValue(details.budget_release_reason) || stringValue(reservation.reason);
  const estimatedCost = stringValue(reservation.estimated_cost_usd) || stringValue(job.metadata.estimated_cost_usd);
  const evidenceStatus = latestEvidenceEvent
    ? eventActionLabel(latestEvidenceEvent.action, t)
    : t("mediaTimelineEmpty");
  const archivedCount = numberValue(archiveSummary.archived_count, numberValue(outputSummary.archived_output_count, 0));
  const downloadableCount = numberValue(outputSummary.downloadable_output_count, job.outputs.length);
  const totalOutputCount = numberValue(outputSummary.output_count, job.outputs.length);
  const skippedCount = numberValue(archiveSummary.skipped_count, 0);

  return (
    <article className="media-execution-evidence">
      <div className="media-execution-evidence-head">
        <div>
          <span>{t("mediaExecutionEvidenceEyebrow")}</span>
          <strong>{t("mediaExecutionEvidenceTitle")}</strong>
        </div>
        <p>{t("mediaExecutionEvidenceSubtitle")}</p>
      </div>
      <div className="media-execution-evidence-grid">
        <EvidenceCard
          detail={budgetReason || t("mediaExecutionBudgetNoReason")}
          label={t("mediaExecutionBudgetEvent")}
          value={eventValueLabel(budgetEvent, t)}
        />
        <EvidenceCard
          detail={estimatedCost ? formatCurrency(estimatedCost) : t("mediaExecutionNoCost")}
          label={t("mediaExecutionBudgetReservation")}
          value={reservation.reservation_id ? shortId(String(reservation.reservation_id)) : "-"}
        />
        <EvidenceCard
          detail={t("mediaExecutionOutputDetail")
            .replace("{{downloadable}}", String(downloadableCount))
            .replace("{{archived}}", String(archivedCount))}
          label={t("mediaExecutionOutputs")}
          value={String(totalOutputCount)}
        />
        <EvidenceCard
          detail={t("mediaExecutionArchiveDetail").replace("{{skipped}}", String(skippedCount))}
          label={t("mediaExecutionArchive")}
          value={archiveSummary.bucket ? String(archiveSummary.bucket) : String(job.output_storage.bucket ?? "-")}
        />
        <EvidenceCard
          detail={latestEvidenceEvent ? formatDateTime(latestEvidenceEvent.created_at) : "-"}
          label={t("mediaExecutionLatestEvidence")}
          value={evidenceStatus}
        />
      </div>
    </article>
  );
}

function EvidenceCard({ detail, label, value }: { detail: string; label: string; value: string }) {
  return (
    <div className="media-execution-evidence-card">
      <span>{label}</span>
      <strong>{value || "-"}</strong>
      <small>{detail || "-"}</small>
    </div>
  );
}

function StorageSummary({ storage }: { storage: Record<string, unknown> }) {
  const { t } = useLocale();
  const entries = Object.entries(storage).filter(([, value]) => value !== null && value !== undefined && value !== "");
  return (
    <article className="media-storage-summary">
      <strong>{t("mediaStorage")}</strong>
      {entries.length ? (
        <dl>
          {entries.map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>{formatUnknown(value)}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="field-help">{t("mediaStorageEmpty")}</p>
      )}
    </article>
  );
}

function DetailBlock({ title, value, tone }: { title: string; value: string; tone?: "error" }) {
  return (
    <article className={tone === "error" ? "media-detail-block error" : "media-detail-block"}>
      <strong>{title}</strong>
      <pre>{value}</pre>
    </article>
  );
}

function assetTitle(asset: Record<string, unknown>, index: number, t: (key: string) => string) {
  const mime = typeof asset.mime_type === "string" ? asset.mime_type : null;
  const kind = typeof asset.kind === "string" ? asset.kind : null;
  return `${t("mediaAsset")} ${index + 1}${kind ? ` · ${kind}` : ""}${mime ? ` · ${mime}` : ""}`;
}

function assetKey(asset: Record<string, unknown>, title: string) {
  const stable =
    stringValue(asset.object_key) ||
    stringValue(asset.url) ||
    stringValue(asset.provider_output_id) ||
    stringValue(asset.checksum_sha256);
  return stable ? `${title}-${stable}` : `${title}-${safeJson(asset)}`;
}

function assetSubtitle(
  asset: Record<string, unknown>,
  kind: "image" | "video" | "reference",
  revealTechnicalDetails: boolean,
  t: (key: string) => string,
) {
  if (!revealTechnicalDetails) {
    return kind === "reference" ? t("mediaReferenceAssetAttached") : t("mediaAssetReady");
  }
  const url = stringValue(asset.url);
  const bucket = stringValue(asset.bucket);
  const objectKey = stringValue(asset.object_key);
  if (url) {
    return url;
  }
  if (bucket || objectKey) {
    return [bucket, objectKey].filter(Boolean).join(" / ");
  }
  return "-";
}

function stringValue(value: unknown) {
  return typeof value === "string" ? value : "";
}

function objectValue(value: unknown) {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function numberValue(value: unknown, fallback: number) {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function latestMediaEvidenceEvent(events: MediaGenerationJobEvent[]) {
  return [...events]
    .reverse()
    .find((event) =>
      ["media.generation.provider_callback", "media.generation.status_update", "media.generation.cancel"].includes(
        event.action,
      ),
    );
}

function eventValueLabel(value: string, t: (key: string) => string) {
  if (value === "settled") {
    return t("mediaExecutionBudgetSettled");
  }
  if (value === "released") {
    return t("mediaExecutionBudgetReleased");
  }
  return value || t("mediaExecutionBudgetReserved");
}

function formatUnknown(value: unknown) {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return safeJson(value);
}

function eventActionLabel(action: string, t: (key: string) => string) {
  const labelKey = MEDIA_EVENT_LABEL_KEYS[action];
  return labelKey ? t(labelKey) : action;
}

const MEDIA_EVENT_LABEL_KEYS: Record<string, string> = {
  "media.generation.cancel": "mediaTimelineCancel",
  "media.generation.create": "mediaTimelineCreate",
  "media.generation.enqueue": "mediaTimelineEnqueue",
  "media.generation.provider_callback": "mediaTimelineProviderCallback",
  "media.generation.provider_callback_ignored": "mediaTimelineProviderCallbackIgnored",
  "media.generation.retry": "mediaTimelineRetry",
  "media.generation.status_update": "mediaTimelineStatusUpdate",
};
