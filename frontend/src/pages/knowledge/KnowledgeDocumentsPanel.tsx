import { Upload, UploadCloud } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button, cx, PageHeader, PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import { KnowledgeAgentBindingPanel } from "./KnowledgeAgentBindingPanel";
import { KnowledgeDocumentTablePanel } from "./KnowledgeDocumentTablePanel";
import { formatKnowledgeVisibilityLabel } from "./knowledgeUtils";
import type { KnowledgeBaseListItem, KnowledgeDocumentListItem } from "./useKnowledgePageController";

type KnowledgeDocumentsTab = "documents" | "binding";

interface KnowledgeDocumentsPanelProps {
  canWrite: boolean;
  documentsError: string | null;
  documentsLoading: boolean;
  documentList: KnowledgeDocumentListItem[];
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  deletingDocumentId: string | null;
  employeeView?: boolean;
  onDeleteDocument: (documentId: string) => void;
  onOpenAgentBinding: () => void;
  onOpenRetrieval: () => void;
  onPickUploadFile: () => void;
  onReingestDocument: (documentId: string) => void;
  onUploadDocumentFile: (file: File) => Promise<void>;
  onUploadFile: (event: React.ChangeEvent<HTMLInputElement>) => void;
  refetchDocuments: () => void;
  reingestingDocumentId: string | null;
  selectedBase: KnowledgeBaseListItem | null;
  uploading: boolean;
}

export function KnowledgeDocumentsPanel({
  canWrite,
  documentsError,
  documentsLoading,
  documentList,
  fileInputRef,
  deletingDocumentId,
  employeeView = false,
  onDeleteDocument,
  onOpenAgentBinding,
  onOpenRetrieval,
  onPickUploadFile,
  onReingestDocument,
  onUploadDocumentFile,
  onUploadFile,
  refetchDocuments,
  reingestingDocumentId,
  selectedBase,
  uploading,
}: KnowledgeDocumentsPanelProps) {
  const { t } = useLocale();
  const [activeTab, setActiveTab] = useState<KnowledgeDocumentsTab>("documents");
  const [isDragOver, setIsDragOver] = useState(false);
  const dragCounterRef = useRef(0);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!e.dataTransfer.types.includes("Files")) return;
    dragCounterRef.current += 1;
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current -= 1;
    if (dragCounterRef.current <= 0) {
      dragCounterRef.current = 0;
      setIsDragOver(false);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer) {
      e.dataTransfer.dropEffect = "copy";
    }
  }, []);

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragCounterRef.current = 0;
      setIsDragOver(false);
      if (uploading || !selectedBase) return;
      const files = Array.from(e.dataTransfer.files);
      if (files.length === 0) return;
      for (const file of files) {
        try {
          await onUploadDocumentFile(file);
        } catch {
          // 错误已由上传函数的 toast 处理，静默继续下一个
        }
      }
    },
    [onUploadDocumentFile, selectedBase, uploading],
  );

  const selectedSubtitle = selectedBase
    ? selectedBaseSubtitle(selectedBase, t, employeeView)
    : t(employeeView ? "knowledgeVisibleResourcesSubtitle" : "knowledgeDocumentsSubtitle");
  const indexedCount = documentList.filter((document) => document.status === "indexed").length;
  const tabs = canWrite
    ? [
        { id: "documents" as const, label: t("knowledgeDocsTabFiles"), description: t("knowledgeDocsTabFilesDesc") },
        { id: "binding" as const, label: t("knowledgeDocsTabBinding"), description: t("knowledgeDocsTabBindingDesc") },
      ]
    : [
        {
          id: "documents" as const,
          label: t("knowledgeDocsTabFiles"),
          description: t("knowledgeDocsTabFilesReadonlyDesc"),
        },
      ];

  useEffect(() => {
    if (!canWrite && activeTab !== "documents") {
      setActiveTab("documents");
    }
  }, [activeTab, canWrite]);

  return (
    <section className="kb-docs">
      <PageHeader
        title={selectedBase?.name ?? t(employeeView ? "knowledgeVisibleResourcesTitle" : "knowledgeDocumentsTitle")}
        subtitle={selectedSubtitle}
        actions={
          <>
            <Button onClick={refetchDocuments} disabled={!selectedBase || documentsLoading}>
              {documentsLoading ? t("knowledgeRefreshing") : t("knowledgeRefresh")}
            </Button>
            {canWrite && (
              <>
                <Button variant="primary" onClick={onPickUploadFile} disabled={!selectedBase || uploading}>
                  <Upload size={16} /> {uploading ? t("knowledgeUploading") : t("knowledgeUpload")}
                </Button>
                <input
                  ref={fileInputRef}
                  className="visually-hidden-file"
                  type="file"
                  accept=".txt,.md,.markdown,.csv,.json,.log,.pdf,.docx,.xlsx"
                  onChange={onUploadFile}
                  disabled={!selectedBase || uploading}
                />
              </>
            )}
          </>
        }
      />
      <div className="nested-workspace kb-docs-workspace">
        <PageTabs active={activeTab} onChange={setActiveTab} tabs={tabs} />
        {activeTab === "documents" && (
          <>
            {canWrite && selectedBase && (
              <section
                className={cx("kb-drop-zone", isDragOver && "drag-over")}
                onDragEnter={handleDragEnter}
                onDragLeave={handleDragLeave}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                aria-label={t("knowledgeDropZoneLabel")}
              >
                <div className="kb-drop-zone-hint">
                  <UploadCloud size={32} aria-hidden="true" />
                  <span>{t("knowledgeDropZoneHint")}</span>
                  <button type="button" className="kb-drop-zone-pick" onClick={onPickUploadFile} disabled={uploading}>
                    {t("knowledgeBrowseFiles")}
                  </button>
                  <span className="kb-drop-zone-formats">{t("knowledgeSupportedFormats")}</span>
                </div>
                {isDragOver && (
                  <div className="kb-drop-zone-overlay">
                    <UploadCloud size={48} aria-hidden="true" />
                    <span>{t("knowledgeReleaseToUpload")}</span>
                  </div>
                )}
              </section>
            )}
            <KnowledgeDocumentTablePanel
              canWrite={canWrite}
              deletingDocumentId={deletingDocumentId}
              documentList={documentList}
              documentsError={documentsError}
              documentsLoading={documentsLoading}
              onDeleteDocument={onDeleteDocument}
              onReingestDocument={onReingestDocument}
              refetchDocuments={refetchDocuments}
              reingestingDocumentId={reingestingDocumentId}
              selectedBase={selectedBase}
            />
          </>
        )}
        {activeTab === "binding" && (
          <KnowledgeAgentBindingPanel
            hasDocuments={documentList.length > 0}
            hasIndexedDocuments={indexedCount > 0}
            onOpenAgentBinding={onOpenAgentBinding}
            onOpenRetrieval={onOpenRetrieval}
            selected={Boolean(selectedBase)}
          />
        )}
      </div>
    </section>
  );
}

function selectedBaseSubtitle(base: KnowledgeBaseListItem, t: (key: string) => string, employeeView: boolean) {
  if ("rag_engine" in base) {
    return t("knowledgeSelectedSubtitle")
      .replace("{{visibility}}", formatKnowledgeVisibilityLabel(base.visibility, t))
      .replace("{{engine}}", base.rag_engine)
      .replace("{{count}}", String(base.document_count));
  }
  if (employeeView) {
    return t("knowledgeVisibleResourcesSelectedSubtitle")
      .replace("{{visibility}}", formatKnowledgeVisibilityLabel(base.visibility, t))
      .replace("{{count}}", String(base.document_count));
  }
  return t("knowledgeSelectedReadonlySubtitle")
    .replace("{{visibility}}", formatKnowledgeVisibilityLabel(base.visibility, t))
    .replace("{{count}}", String(base.document_count));
}
