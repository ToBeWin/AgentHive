import { StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type {
  DocumentUploadCompleteResponse,
  KnowledgeBaseResponse,
  KnowledgeDocumentResponse,
  RetrievalTestResponse,
} from "../../lib/api";
import { KnowledgeHandoffChecklistPanel } from "./KnowledgeHandoffChecklistPanel";
import { KnowledgeReadinessPanel } from "./KnowledgeReadinessPanel";
import { formatBytes, formatKnowledgeStatus } from "./knowledgeUtils";

interface KnowledgeDocumentReadinessPanelProps {
  actionError: string | null;
  documents: KnowledgeDocumentResponse[];
  onOpenAgentBinding: () => void;
  onOpenDocuments: () => void;
  onOpenRetrieval: () => void;
  onPickUploadFile: () => void;
  retrievalResult: RetrievalTestResponse | null;
  selectedBase: KnowledgeBaseResponse | null;
  uploadResult: DocumentUploadCompleteResponse | null;
}

export function KnowledgeDocumentReadinessPanel({
  actionError,
  documents,
  onOpenAgentBinding,
  onOpenDocuments,
  onOpenRetrieval,
  onPickUploadFile,
  retrievalResult,
  selectedBase,
  uploadResult,
}: KnowledgeDocumentReadinessPanelProps) {
  const { t } = useLocale();

  return (
    <div className="kb-docs-section">
      <KnowledgeReadinessPanel documents={documents} selectedBase={selectedBase} />
      <KnowledgeHandoffChecklistPanel
        documents={documents}
        onOpenAgentBinding={onOpenAgentBinding}
        onOpenDocuments={onOpenDocuments}
        onOpenRetrieval={onOpenRetrieval}
        onPickUploadFile={onPickUploadFile}
        retrievalResult={retrievalResult}
        selectedBase={selectedBase}
        uploadResult={uploadResult}
      />
      {uploadResult && (
        <div className="upload-result">
          <div>
            <strong>{uploadResult.document.filename}</strong>
            <span>
              {formatBytes(uploadResult.document.size_bytes, t("knowledgeSizePending"))} · {t("knowledgeAutoIngest")}{" "}
              {uploadResult.auto_ingest ? t("knowledgeAutoIngestEnabled") : t("knowledgeAutoIngestDisabled")}
            </span>
          </div>
          <StatusBadge status={formatKnowledgeStatus(uploadResult.ingest_status ?? uploadResult.document.status)} />
          <p>{uploadResult.message}</p>
        </div>
      )}
      {actionError && <div className="form-message error">{actionError}</div>}
    </div>
  );
}
