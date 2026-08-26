import { AlertTriangle, CheckCircle2, Database, FileSearch, Loader2 } from "lucide-react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { KnowledgeBaseResponse, KnowledgeDocumentResponse } from "../../lib/api";
import { formatBytes } from "./knowledgeUtils";

interface KnowledgeReadinessPanelProps {
  documents: KnowledgeDocumentResponse[];
  selectedBase: KnowledgeBaseResponse | null;
}

export function KnowledgeReadinessPanel({ documents, selectedBase }: KnowledgeReadinessPanelProps) {
  const { t } = useLocale();
  const readiness = getReadinessState(documents, selectedBase, t);
  const Icon = readiness.icon;

  return (
    <section className={cx("knowledge-readiness-panel", readiness.kind)}>
      <div className="knowledge-readiness-header">
        <span className="knowledge-readiness-icon">
          <Icon size={18} />
        </span>
        <div>
          <h2>{t("knowledgeReadinessTitle")}</h2>
          <p>{readiness.message}</p>
        </div>
        <StatusBadge label={readiness.label} status={readiness.status} />
      </div>
      <div className="knowledge-readiness-grid">
        <ReadinessMetric label={t("knowledgeReadyDocuments")} value={String(readiness.indexedCount)} />
        <ReadinessMetric label={t("knowledgeProcessingDocuments")} value={String(readiness.processingCount)} />
        <ReadinessMetric label={t("knowledgeFailedDocuments")} value={String(readiness.failedCount)} />
        <ReadinessMetric label={t("knowledgeTotalChunks")} value={readiness.totalChunks.toLocaleString()} />
        <ReadinessMetric label={t("knowledgeStorageFootprint")} value={formatBytes(readiness.totalBytes, "0 B")} />
        <ReadinessMetric
          label={t("knowledgeLastIndexed")}
          value={readiness.lastIndexedAt ?? t("knowledgeNotReadyYet")}
        />
      </div>
      <div className="knowledge-readiness-footer">
        <span>
          <Database size={14} /> {t("knowledgeStorageBoundary")} MinIO
        </span>
        <span>
          <FileSearch size={14} /> {t("knowledgeVectorBoundary")} pgvector
        </span>
        <span>
          {selectedBase ? `${t("knowledgeRagEngine")} ${selectedBase.rag_engine}` : t("knowledgeSelectBaseToRun")}
        </span>
      </div>
    </section>
  );
}

function ReadinessMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="knowledge-readiness-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function getReadinessState(
  documents: KnowledgeDocumentResponse[],
  selectedBase: KnowledgeBaseResponse | null,
  t: (key: string) => string,
) {
  const indexedCount = documents.filter((document) => document.status === "indexed").length;
  const failedCount = documents.filter((document) => document.status === "failed").length;
  const processingCount = documents.filter((document) =>
    ["pending_upload", "uploaded", "ingesting"].includes(document.status),
  ).length;
  const totalChunks = documents.reduce((sum, document) => sum + document.chunk_count, 0);
  const totalBytes = documents.reduce((sum, document) => sum + (document.size_bytes ?? 0), 0);
  const indexedDates = documents
    .filter((document) => document.status === "indexed")
    .map((document) => new Date(document.updated_at))
    .filter((date) => !Number.isNaN(date.getTime()))
    .sort((left, right) => right.getTime() - left.getTime());
  const lastIndexedAt = indexedDates[0]?.toLocaleString();

  if (!selectedBase) {
    return {
      failedCount,
      icon: FileSearch,
      indexedCount,
      kind: "empty",
      label: t("knowledgeReadinessNotReady"),
      lastIndexedAt,
      message: t("knowledgeReadinessSelectBase"),
      processingCount,
      status: "inactive",
      totalBytes,
      totalChunks,
    };
  }
  if (!documents.length) {
    return {
      failedCount,
      icon: FileSearch,
      indexedCount,
      kind: "empty",
      label: t("knowledgeReadinessEmpty"),
      lastIndexedAt,
      message: t("knowledgeReadinessUploadDocuments"),
      processingCount,
      status: "inactive",
      totalBytes,
      totalChunks,
    };
  }
  if (failedCount > 0) {
    return {
      failedCount,
      icon: AlertTriangle,
      indexedCount,
      kind: "error",
      label: t("knowledgeReadinessNeedsAttention"),
      lastIndexedAt,
      message: t("knowledgeReadinessFailedMessage"),
      processingCount,
      status: "failed",
      totalBytes,
      totalChunks,
    };
  }
  if (processingCount > 0) {
    return {
      failedCount,
      icon: Loader2,
      indexedCount,
      kind: "warning",
      label: t("knowledgeReadinessProcessing"),
      lastIndexedAt,
      message: t("knowledgeReadinessProcessingMessage"),
      processingCount,
      status: "warning",
      totalBytes,
      totalChunks,
    };
  }
  return {
    failedCount,
    icon: CheckCircle2,
    indexedCount,
    kind: "ready",
    label: t("knowledgeReadinessReady"),
    lastIndexedAt,
    message: t("knowledgeReadinessReadyMessage"),
    processingCount,
    status: "ready",
    totalBytes,
    totalChunks,
  };
}
