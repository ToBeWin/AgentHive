import { FileText } from "lucide-react";
import { Button, cx, EmptyState, StatusBadge } from "../../components/app-ui";
import { TablePagination } from "../../components/TablePagination";
import { useLocale } from "../../i18n-context";
import type { AuditLogItem } from "../../lib/api";
import { formatDateTime } from "../../lib/formatters";
import { auditStatusLabel, compactDetails, compactIdentifier, compactResource } from "./auditUtils";

export function AuditLogTable({
  hasNextPage,
  hasPreviousPage,
  limit,
  offset,
  onNextPage,
  onPreviousPage,
  onSelectEvent,
  rows,
  selectedEventId,
  total,
}: {
  hasNextPage: boolean;
  hasPreviousPage: boolean;
  limit: number;
  offset: number;
  onNextPage: () => void;
  onPreviousPage: () => void;
  onSelectEvent: (eventId: string) => void;
  rows: AuditLogItem[];
  selectedEventId: string | null;
  total: number;
}) {
  const { locale, t } = useLocale();
  const currentPage = Math.floor(offset / limit) + 1;

  const handlePageChange = (nextPage: number) => {
    if (nextPage > currentPage && hasNextPage) {
      onNextPage();
    } else if (nextPage < currentPage && hasPreviousPage) {
      onPreviousPage();
    }
  };

  return (
    <section className="panel table-panel">
      <table className="data-table audit-table">
        <thead>
          <tr>
            <th>{t("auditTimestamp")}</th>
            <th>{t("auditActor")}</th>
            <th>{t("auditActionType")}</th>
            <th>{t("auditResource")}</th>
            <th>{t("auditStatus")}</th>
            <th>{t("auditIpAddress")}</th>
            <th>{t("auditDetails")}</th>
            <th>{t("auditActions")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.id}
              className={cx(row.status !== "success" && "error-row", selectedEventId === row.id && "selected-row")}
            >
              <td>
                <code>{formatDateTime(row.created_at, locale)}</code>
              </td>
              <td className="audit-identity-cell" title={row.actor_id ?? row.actor_type}>
                {row.actor_id ? compactIdentifier(row.actor_id) : row.actor_type}
              </td>
              <td className="audit-compact-cell" title={row.action}>
                {row.action}
                {row.request_id && <span className="row-subtitle">{row.request_id}</span>}
              </td>
              <td
                className="audit-compact-cell"
                title={row.resource_id ?? row.resource_type ?? t("auditSystemResource")}
              >
                <code>{compactResource(row, t("auditSystemResource"))}</code>
              </td>
              <td>
                <StatusBadge status={auditStatusLabel(row.status, t)} />
              </td>
              <td className="audit-compact-cell" title={row.ip_address ?? "-"}>
                <code>{row.ip_address ?? "-"}</code>
              </td>
              <td className="audit-details-cell" title={JSON.stringify(row.details)}>
                {compactDetails(row.details, t("auditNoDetails"))}
              </td>
              <td>
                <Button onClick={() => onSelectEvent(row.id)}>{t("auditViewDetails")}</Button>
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td className="table-empty-cell" colSpan={8}>
                <EmptyState icon={<FileText />} title={t("emptyTitleAudit")} message={t("auditEmpty")} />
              </td>
            </tr>
          )}
        </tbody>
      </table>
      <TablePagination total={total} page={currentPage} pageSize={limit} onPageChange={handlePageChange} />
    </section>
  );
}
