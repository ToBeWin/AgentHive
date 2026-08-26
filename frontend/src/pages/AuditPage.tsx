import { Download } from "lucide-react";
import { useMemo, useState } from "react";
import { ApiNotice, Button, cx, LoadingState, PageHeader } from "../components/app-ui";
import { prototypeAuditLogExport, useAuditLogs } from "../hooks/useAdminData";
import { useLocale } from "../i18n-context";
import { type AuthUser, adminApi } from "../lib/api";
import { downloadTextFile } from "../lib/download";
import { canAccess } from "../lib/permissions";
import { AuditEventDetailsPanel } from "./audit/AuditEventDetailsPanel";
import { AuditFiltersPanel } from "./audit/AuditFiltersPanel";
import { AuditLogTable } from "./audit/AuditLogTable";
import { AuditSummaryGrid } from "./audit/AuditSummaryGrid";
import { type AuditFilterState, emptyAuditFilters, toAuditQueryFilters } from "./audit/auditUtils";

const AUDIT_EXPORT_PERMISSION = "audit:export";
const AUDIT_PAGE_SIZE = 50;

export function AuditPage({ isPrototype = false, user }: { isPrototype?: boolean; user: AuthUser | null }) {
  const { t } = useLocale();
  const [filters, setFilters] = useState<AuditFilterState>(emptyAuditFilters);
  const [page, setPage] = useState(0);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const queryFilters = useMemo(
    () => toAuditQueryFilters(filters, { limit: AUDIT_PAGE_SIZE, offset: page * AUDIT_PAGE_SIZE }),
    [filters, page],
  );
  const exportFilters = useMemo(() => toAuditQueryFilters(filters), [filters]);
  const audit = useAuditLogs(queryFilters, { fallbackOnError: isPrototype });
  const rows = audit.data?.items ?? [];
  const total = audit.data?.total ?? 0;
  const selectedEvent = rows.find((row) => row.id === selectedEventId) ?? null;
  const canExportAudit = isPrototype || canAccess(user, [AUDIT_EXPORT_PERMISSION]);
  const hasPreviousPage = page > 0;
  const hasNextPage = (page + 1) * AUDIT_PAGE_SIZE < total;

  const handleFiltersChange = (nextFilters: AuditFilterState) => {
    setFilters(nextFilters);
    setPage(0);
    setSelectedEventId(null);
  };

  const handlePreviousPage = () => {
    setPage((current) => Math.max(0, current - 1));
    setSelectedEventId(null);
  };

  const handleNextPage = () => {
    setPage((current) => current + 1);
    setSelectedEventId(null);
  };

  const handleExportCsv = async () => {
    await exportAuditFile({
      extension: "csv",
      exporter: () =>
        isPrototype
          ? Promise.resolve(prototypeAuditLogExport(exportFilters, "csv"))
          : adminApi.exportAuditLogsCsv(exportFilters),
      mimeType: "text/csv;charset=utf-8",
      setExportError,
      setExporting,
      t,
    });
  };

  const handleExportJson = async () => {
    await exportAuditFile({
      extension: "json",
      exporter: () =>
        isPrototype
          ? Promise.resolve(prototypeAuditLogExport(exportFilters, "json"))
          : adminApi.exportAuditLogsJson(exportFilters),
      mimeType: "application/json;charset=utf-8",
      setExportError,
      setExporting,
      t,
    });
  };

  return (
    <section className="page audit-page">
      <PageHeader
        title={t("auditTitle")}
        subtitle={t("auditSubtitleSlim")}
        actions={
          canExportAudit ? (
            <>
              <Button onClick={handleExportCsv} disabled={exporting}>
                <Download size={16} /> {exporting ? t("auditExporting") : t("auditExportCsv")}
              </Button>
              <Button onClick={handleExportJson} disabled={exporting}>
                <Download size={16} /> {exporting ? t("auditExporting") : t("auditExportJson")}
              </Button>
            </>
          ) : undefined
        }
      />
      {exportError && <ApiNotice title={t("auditExportFailedTitle")} message={exportError} />}
      {audit.loading && !rows.length && <LoadingState message={t("auditLoadingMessage")} lines={3} />}
      {audit.loading && !!rows.length && (
        <div className="refresh-indicator" role="status" aria-live="polite">
          <span className="refresh-spinner" aria-hidden="true" />
          {t("commonRefreshing")}
        </div>
      )}
      {audit.error && !audit.loading && (
        <ApiNotice
          title={t("auditLoadErrorTitle")}
          message={audit.error}
          action={<Button onClick={audit.refetch}>{t("commonRetry")}</Button>}
        />
      )}
      <AuditSummaryGrid rows={rows} total={total} />
      <AuditFiltersPanel filters={filters} onChange={handleFiltersChange} />
      <div className={cx("audit-events-layout", selectedEvent ? "details-open" : undefined)}>
        <AuditLogTable
          limit={AUDIT_PAGE_SIZE}
          offset={page * AUDIT_PAGE_SIZE}
          onNextPage={handleNextPage}
          onPreviousPage={handlePreviousPage}
          onSelectEvent={setSelectedEventId}
          rows={rows}
          selectedEventId={selectedEventId}
          total={total}
          hasNextPage={hasNextPage}
          hasPreviousPage={hasPreviousPage}
        />
        {selectedEvent ? (
          <AuditEventDetailsPanel event={selectedEvent} onClose={() => setSelectedEventId(null)} />
        ) : null}
      </div>
    </section>
  );
}

async function exportAuditFile({
  extension,
  exporter,
  mimeType,
  setExportError,
  setExporting,
  t,
}: {
  extension: "csv" | "json";
  exporter: () => Promise<string>;
  mimeType: string;
  setExportError: (value: string | null) => void;
  setExporting: (value: boolean) => void;
  t: (key: string) => string;
}) {
  setExporting(true);
  setExportError(null);
  try {
    const content = await exporter();
    downloadTextFile(content, `agenthive-audit-${new Date().toISOString().slice(0, 10)}.${extension}`, mimeType);
  } catch (error) {
    setExportError(error instanceof Error ? error.message : t("auditExportFailedMessage"));
  } finally {
    setExporting(false);
  }
}
