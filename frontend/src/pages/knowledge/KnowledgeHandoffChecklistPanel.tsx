import { Bot, CheckCircle2, Database, FileSearch, type LucideIcon, ShieldCheck, UploadCloud } from "lucide-react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type {
  DocumentUploadCompleteResponse,
  KnowledgeBaseResponse,
  KnowledgeDocumentResponse,
  RetrievalTestResponse,
} from "../../lib/api";

interface KnowledgeHandoffChecklistPanelProps {
  documents: KnowledgeDocumentResponse[];
  onOpenAgentBinding: () => void;
  onOpenDocuments: () => void;
  onOpenRetrieval: () => void;
  onPickUploadFile: () => void;
  retrievalResult: RetrievalTestResponse | null;
  selectedBase: KnowledgeBaseResponse | null;
  uploadResult: DocumentUploadCompleteResponse | null;
}

export function KnowledgeHandoffChecklistPanel({
  documents,
  onOpenAgentBinding,
  onOpenDocuments,
  onOpenRetrieval,
  onPickUploadFile,
  retrievalResult,
  selectedBase,
  uploadResult,
}: KnowledgeHandoffChecklistPanelProps) {
  const { t } = useLocale();
  const indexedDocuments = documents.filter((document) => document.status === "indexed");
  const failedDocuments = documents.filter((document) => document.status === "failed");
  const processingDocuments = documents.filter((document) =>
    ["pending_upload", "uploaded", "ingesting"].includes(document.status),
  );
  const totalChunks = indexedDocuments.reduce((sum, document) => sum + document.chunk_count, 0);
  const retrievalVerified =
    Boolean(selectedBase) &&
    retrievalResult?.knowledge_base_id === selectedBase?.id &&
    (retrievalResult?.results.length ?? 0) > 0;
  const uploadEvidence = Boolean(uploadResult?.document.id);
  const checks: Array<{
    action: () => void;
    detail: string;
    icon: LucideIcon;
    id: "base" | "documents" | "storage" | "retrieval" | "binding";
    metric: string;
    status: string;
    title: string;
    tone: "ok" | "warning" | "blocked";
  }> = [
    {
      action: onOpenDocuments,
      detail: selectedBase ? t("knowledgeChecklistBaseDetail") : t("knowledgeChecklistBaseMissingDetail"),
      icon: Database,
      id: "base",
      metric: selectedBase ? selectedBase.name : t("knowledgeLoopNoBase"),
      status: selectedBase ? t("knowledgeChecklistPassed") : t("knowledgeChecklistBlocked"),
      title: t("knowledgeChecklistBase"),
      tone: selectedBase ? "ok" : "blocked",
    },
    {
      action: indexedDocuments.length ? onOpenDocuments : onPickUploadFile,
      detail: t("knowledgeChecklistDocumentsDetail")
        .replace("{{processing}}", String(processingDocuments.length))
        .replace("{{failed}}", String(failedDocuments.length)),
      icon: UploadCloud,
      id: "documents",
      metric: t("knowledgeChecklistDocumentsMetric")
        .replace("{{indexed}}", String(indexedDocuments.length))
        .replace("{{total}}", String(documents.length)),
      status: indexedDocuments.length ? t("knowledgeChecklistPassed") : t("knowledgeChecklistNeedsDocuments"),
      title: t("knowledgeChecklistDocuments"),
      tone: indexedDocuments.length ? (failedDocuments.length ? "warning" : "ok") : "blocked",
    },
    {
      action: onOpenDocuments,
      detail: t("knowledgeChecklistStorageDetail").replace("{{chunks}}", String(totalChunks)),
      icon: ShieldCheck,
      id: "storage",
      metric: uploadEvidence ? t("knowledgeChecklistStorageEvidence") : t("knowledgeChecklistStoragePending"),
      status:
        uploadEvidence || indexedDocuments.length ? t("knowledgeChecklistPassed") : t("knowledgeChecklistNeedsUpload"),
      title: t("knowledgeChecklistStorage"),
      tone: uploadEvidence || indexedDocuments.length ? "ok" : selectedBase ? "warning" : "blocked",
    },
    {
      action: onOpenRetrieval,
      detail: t("knowledgeChecklistRetrievalDetail").replace("{{count}}", String(retrievalResult?.results.length ?? 0)),
      icon: FileSearch,
      id: "retrieval",
      metric: retrievalVerified ? t("knowledgeChecklistRetrievalVerified") : t("knowledgeChecklistRetrievalMissing"),
      status: retrievalVerified ? t("knowledgeChecklistPassed") : t("knowledgeChecklistNeedsRetrieval"),
      title: t("knowledgeChecklistRetrieval"),
      tone: retrievalVerified ? "ok" : indexedDocuments.length ? "warning" : "blocked",
    },
    {
      action: onOpenAgentBinding,
      detail: t("knowledgeChecklistBindingDetail"),
      icon: Bot,
      id: "binding",
      metric: retrievalVerified ? t("knowledgeChecklistBindingReady") : t("knowledgeChecklistBindingPending"),
      status: retrievalVerified ? t("knowledgeChecklistPassed") : t("knowledgeChecklistNeedsBinding"),
      title: t("knowledgeChecklistBinding"),
      tone: retrievalVerified ? "ok" : indexedDocuments.length ? "warning" : "blocked",
    },
  ];
  const passed = checks.filter((check) => check.tone === "ok").length;

  return (
    <section className="knowledge-handoff-checklist" aria-label={t("knowledgeChecklistTitle")}>
      <div className="knowledge-handoff-checklist-head">
        <span className="knowledge-handoff-checklist-icon">
          <CheckCircle2 size={18} />
        </span>
        <div>
          <span>{t("knowledgeChecklistEyebrow")}</span>
          <strong>{t("knowledgeChecklistTitle")}</strong>
          <p>
            {t("knowledgeChecklistDescription")
              .replace("{{passed}}", String(passed))
              .replace("{{total}}", String(checks.length))}
          </p>
        </div>
        <StatusBadge
          label={passed === checks.length ? t("knowledgeChecklistReady") : t("knowledgeChecklistNeedsReview")}
          status={passed === checks.length ? "ready" : "warning"}
        />
      </div>
      <div className="knowledge-handoff-checklist-grid">
        {checks.map((check) => {
          const Icon = check.icon;
          return (
            <button
              className={cx("knowledge-handoff-checklist-card", check.tone)}
              disabled={!selectedBase && check.id !== "base"}
              key={check.id}
              onClick={check.action}
              type="button"
            >
              <span className="knowledge-handoff-checklist-card-icon">
                <Icon size={17} />
              </span>
              <span className="knowledge-handoff-checklist-copy">
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
