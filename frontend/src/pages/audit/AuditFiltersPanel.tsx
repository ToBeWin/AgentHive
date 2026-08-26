import { Button } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import { type AuditFilterState, auditStatusLabel, emptyAuditFilters } from "./auditUtils";

export function AuditFiltersPanel({
  filters,
  onChange,
}: {
  filters: AuditFilterState;
  onChange: (filters: AuditFilterState) => void;
}) {
  const { t } = useLocale();
  const activeFilters = activeAuditFilters(filters, t);
  const activeCount = activeFilters.length;
  const summary = activeCount ? activeFilters.slice(0, 3).join(" / ") : t("auditFilterNoActive");

  return (
    <details className="panel audit-filter-panel" open={activeCount > 0}>
      <summary className="audit-filter-summary">
        <div>
          <strong>{t("auditFilterPanelTitle")}</strong>
          <small>{summary}</small>
        </div>
        <span>
          {t("auditFilterActiveCount").replace("{{count}}", String(activeCount))}
          {activeCount > 3 ? ` · ${t("auditFilterMore").replace("{{count}}", String(activeCount - 3))}` : ""}
        </span>
      </summary>
      <div className="filters-row audit-filters">
        <label>
          {t("auditAction")}
          <input
            placeholder={t("auditActionPlaceholder")}
            value={filters.action}
            onChange={(event) => onChange({ ...filters, action: event.target.value })}
          />
        </label>
        <label>
          {t("auditStatusFilter")}
          <select value={filters.status} onChange={(event) => onChange({ ...filters, status: event.target.value })}>
            <option value="">{t("auditAllStatuses")}</option>
            <option value="success">{auditStatusLabel("success", t)}</option>
            <option value="failed">{auditStatusLabel("failed", t)}</option>
            <option value="denied">{auditStatusLabel("denied", t)}</option>
            <option value="error">{auditStatusLabel("error", t)}</option>
          </select>
        </label>
        <label>
          {t("auditActorId")}
          <input
            placeholder={t("auditActorPlaceholder")}
            value={filters.actor_id}
            onChange={(event) => onChange({ ...filters, actor_id: event.target.value })}
          />
        </label>
        <label>
          {t("auditResourceType")}
          <input
            placeholder={t("auditResourcePlaceholder")}
            value={filters.resource_type}
            onChange={(event) => onChange({ ...filters, resource_type: event.target.value })}
          />
        </label>
        <label>
          {t("auditRequestId")}
          <input
            placeholder={t("auditRequestPlaceholder")}
            value={filters.request_id}
            onChange={(event) => onChange({ ...filters, request_id: event.target.value })}
          />
        </label>
        <label>
          {t("auditCreatedFrom")}
          <input
            type="datetime-local"
            value={filters.created_from}
            onChange={(event) => onChange({ ...filters, created_from: event.target.value })}
          />
        </label>
        <label>
          {t("auditCreatedTo")}
          <input
            type="datetime-local"
            value={filters.created_to}
            onChange={(event) => onChange({ ...filters, created_to: event.target.value })}
          />
        </label>
        <Button onClick={() => onChange(emptyAuditFilters)}>{t("auditClearFilters")}</Button>
      </div>
    </details>
  );
}

function activeAuditFilters(filters: AuditFilterState, t: (key: string) => string) {
  const active: string[] = [];
  if (filters.action.trim()) {
    active.push(`${t("auditAction")}: ${filters.action.trim()}`);
  }
  if (filters.status.trim()) {
    active.push(`${t("auditStatusFilter")}: ${auditStatusLabel(filters.status.trim(), t)}`);
  }
  if (filters.actor_id.trim()) {
    active.push(`${t("auditActorId")}: ${filters.actor_id.trim()}`);
  }
  if (filters.resource_type.trim()) {
    active.push(`${t("auditResourceType")}: ${filters.resource_type.trim()}`);
  }
  if (filters.request_id.trim()) {
    active.push(`${t("auditRequestId")}: ${filters.request_id.trim()}`);
  }
  if (filters.created_from.trim()) {
    active.push(`${t("auditCreatedFrom")}: ${filters.created_from.trim()}`);
  }
  if (filters.created_to.trim()) {
    active.push(`${t("auditCreatedTo")}: ${filters.created_to.trim()}`);
  }
  return active;
}
