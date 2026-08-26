import { FileText, FolderOpen, RefreshCw, Search, Trash2, X } from "lucide-react";
import { useMemo, useState } from "react";
import { ApiNotice, Button, ConfirmDialog, EmptyState, StatusBadge } from "../../components/app-ui";
import { DEFAULT_PAGE_SIZE, paginate, TablePagination } from "../../components/TablePagination";
import { useLocale } from "../../i18n-context";
import { documentFileType, formatBytes, formatKnowledgeStatus } from "./knowledgeUtils";
import type { KnowledgeBaseListItem, KnowledgeDocumentListItem } from "./useKnowledgePageController";

interface KnowledgeDocumentTablePanelProps {
  canWrite: boolean;
  deletingDocumentId: string | null;
  documentsError: string | null;
  documentsLoading: boolean;
  documentList: KnowledgeDocumentListItem[];
  onDeleteDocument: (documentId: string) => void;
  onReingestDocument: (documentId: string) => void;
  refetchDocuments: () => void;
  reingestingDocumentId: string | null;
  selectedBase: KnowledgeBaseListItem | null;
}

export function KnowledgeDocumentTablePanel({
  canWrite,
  deletingDocumentId,
  documentsError,
  documentsLoading,
  documentList,
  onDeleteDocument,
  onReingestDocument,
  refetchDocuments,
  reingestingDocumentId,
  selectedBase,
}: KnowledgeDocumentTablePanelProps) {
  const { t } = useLocale();
  const [pendingDeleteDoc, setPendingDeleteDoc] = useState<KnowledgeDocumentListItem | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "indexed" | "processing" | "failed">("all");
  const columnCount = canWrite ? 5 : 4;

  const filteredDocuments = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return documentList.filter((document) => {
      const isProcessing = document.status === "ingesting" || document.status === "pending_upload";
      const matchesQuery = [document.filename, document.source, document.status]
        .join(" ")
        .toLocaleLowerCase()
        .includes(normalizedQuery);
      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "indexed" && document.status === "indexed") ||
        (statusFilter === "processing" && isProcessing) ||
        (statusFilter === "failed" && document.status === "failed");
      return matchesQuery && matchesStatus;
    });
  }, [documentList, query, statusFilter]);

  const datasetKey = `${selectedBase?.id ?? ""}:${documentList.length}:${query}:${statusFilter}`;
  const [lastDatasetKey, setLastDatasetKey] = useState(datasetKey);
  if (datasetKey !== lastDatasetKey) {
    setLastDatasetKey(datasetKey);
    setPage(1);
  }

  const totalPages = Math.max(1, Math.ceil(filteredDocuments.length / pageSize));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const pagedDocuments = paginate(filteredDocuments, { page: safePage, pageSize });

  const confirmDeleteDoc = () => {
    const target = pendingDeleteDoc;
    setPendingDeleteDoc(null);
    if (target) {
      onDeleteDocument(target.id);
    }
  };

  return (
    <div className="kb-docs-section">
      <div className="inline-note">{canWrite ? t("knowledgeUploadNote") : t("knowledgeReadonlyDocumentNote")}</div>
      <div className="collection-toolbar knowledge-document-toolbar">
        <label className="collection-search">
          <Search size={16} aria-hidden="true" />
          <span className="visually-hidden">{t("knowledgeSearchDocumentsLabel")}</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("knowledgeSearchDocumentsPlaceholder")}
            aria-label={t("knowledgeSearchDocumentsLabel")}
          />
          {query && (
            <button
              className="collection-search-clear"
              type="button"
              onClick={() => setQuery("")}
              aria-label={t("commonClearSearch")}
              title={t("commonClearSearch")}
            >
              <X size={14} aria-hidden="true" />
            </button>
          )}
        </label>
        <label className="collection-filter">
          <span>{t("knowledgeDocumentFilterLabel")}</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}>
            <option value="all">{t("knowledgeDocumentFilterAll")}</option>
            <option value="indexed">{t("knowledgeDocumentFilterIndexed")}</option>
            <option value="processing">{t("knowledgeDocumentFilterProcessing")}</option>
            <option value="failed">{t("knowledgeDocumentFilterFailed")}</option>
          </select>
        </label>
        <span className="collection-toolbar-meta">
          {t("knowledgeDocumentResults")
            .replace("{{visible}}", String(filteredDocuments.length))
            .replace("{{total}}", String(documentList.length))}
        </span>
      </div>
      {documentsError && (
        <ApiNotice
          title={t("knowledgeDocumentsUnavailable")}
          message={documentsError}
          action={<Button onClick={refetchDocuments}>{t("commonRetry")}</Button>}
        />
      )}
      <table className="data-table knowledge-doc-table">
        <thead>
          <tr>
            <th>{t("knowledgeFileName")}</th>
            <th>{t("knowledgeType")}</th>
            <th>{t("knowledgeChunks")}</th>
            <th>{t("knowledgeStatus")}</th>
            {canWrite && <th>{t("knowledgeActions")}</th>}
          </tr>
        </thead>
        <tbody>
          {documentsLoading && (
            <tr>
              <td className="table-empty-cell" colSpan={columnCount}>
                {t("knowledgeLoadingDocuments")}
              </td>
            </tr>
          )}
          {!documentsLoading && selectedBase && !documentList.length && (
            <tr>
              <td className="table-empty-cell" colSpan={columnCount}>
                <EmptyState icon={<FileText />} title={t("knowledgeNoDocuments")} />
              </td>
            </tr>
          )}
          {!documentsLoading && selectedBase && documentList.length > 0 && !filteredDocuments.length && (
            <tr>
              <td className="table-empty-cell" colSpan={columnCount}>
                <EmptyState
                  icon={<Search />}
                  title={t("knowledgeNoDocumentMatches")}
                  message={t("knowledgeNoDocumentMatchesDetail")}
                />
              </td>
            </tr>
          )}
          {!documentsLoading && !selectedBase && (
            <tr>
              <td className="table-empty-cell" colSpan={columnCount}>
                <EmptyState
                  icon={<FolderOpen />}
                  title={canWrite ? t("knowledgeCreateBaseFirst") : t("knowledgeSelectVisibleBaseFirst")}
                />
              </td>
            </tr>
          )}
          {pagedDocuments.map((doc) => {
            const reingestDisabled =
              !canWrite ||
              reingestingDocumentId === doc.id ||
              doc.status === "pending_upload" ||
              doc.status === "ingesting";

            return (
              <tr key={doc.id}>
                <td>
                  <FileText size={16} />
                  <div className="document-file-cell">
                    <strong>{doc.filename}</strong>
                    <small>
                      {formatBytes(doc.size_bytes, t("knowledgeSizePending"))} · {doc.source.replace(/_/g, " ")}
                    </small>
                    {canWrite && "storage_bucket" in doc && (
                      <StorageDetail
                        bucket={doc.storage_bucket}
                        objectKey={doc.storage_object_key}
                        objectKeyLabel={t("knowledgeObjectKey")}
                        storageLabel={t("knowledgeStorage")}
                      />
                    )}
                  </div>
                </td>
                <td>{documentFileType(doc)}</td>
                <td>{doc.chunk_count}</td>
                <td>
                  <StatusBadge status={formatKnowledgeStatus(doc.status)} />
                  {canWrite && "error_message" in doc && doc.error_message && <small>{doc.error_message}</small>}
                </td>
                {canWrite && (
                  <td>
                    <div className="table-actions">
                      <Button onClick={() => onReingestDocument(doc.id)} disabled={reingestDisabled}>
                        <RefreshCw size={15} />{" "}
                        {reingestingDocumentId === doc.id ? t("knowledgeReingesting") : t("knowledgeReingestDocument")}
                      </Button>
                      <Button onClick={() => setPendingDeleteDoc(doc)} disabled={deletingDocumentId === doc.id}>
                        <Trash2 size={15} />{" "}
                        {deletingDocumentId === doc.id ? t("knowledgeDeleting") : t("knowledgeDeleteDocument")}
                      </Button>
                    </div>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
      <TablePagination
        total={filteredDocuments.length}
        page={safePage}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
        }}
      />
      <ConfirmDialog
        open={Boolean(pendingDeleteDoc)}
        title={t("knowledgeDeleteDocument")}
        message={pendingDeleteDoc ? t("knowledgeDeleteDocumentConfirm") : ""}
        confirmLabel={t("knowledgeDeleteDocument")}
        cancelLabel={t("commonClose")}
        variant="danger"
        onConfirm={confirmDeleteDoc}
        onCancel={() => setPendingDeleteDoc(null)}
      />
    </div>
  );
}

function StorageDetail({
  bucket,
  objectKey,
  objectKeyLabel,
  storageLabel,
}: {
  bucket: string;
  objectKey: string;
  objectKeyLabel: string;
  storageLabel: string;
}) {
  return (
    <span className="storage-detail">
      <code title={`${storageLabel}: ${bucket}`}>{bucket}</code>
      <small title={`${objectKeyLabel}: ${objectKey}`}>{objectKey}</small>
    </span>
  );
}
