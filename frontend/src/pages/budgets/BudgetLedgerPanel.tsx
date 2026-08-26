import { Download } from "lucide-react";
import { ApiNotice, Button, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { BudgetLedgerItem } from "../../lib/api";
import { formatCurrency, formatDateTime, formatNumber } from "../../lib/formatters";

export function BudgetLedgerPanel({
  canExport,
  error,
  exporting,
  items,
  loading,
  onExportCsv,
  onExportJson,
  onRetry,
}: {
  canExport: boolean;
  error: string | null;
  exporting: boolean;
  items: BudgetLedgerItem[];
  loading: boolean;
  onExportCsv: () => void;
  onExportJson: () => void;
  onRetry: () => void;
}) {
  const { locale, t } = useLocale();
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>{t("budgetsRecentBudgetLedger")}</h2>
        {canExport ? (
          <div className="panel-actions">
            <Button variant="ghost" onClick={onExportCsv} disabled={exporting}>
              <Download size={16} /> {exporting ? t("budgetsExporting") : t("budgetsExportCsv")}
            </Button>
            <Button variant="ghost" onClick={onExportJson} disabled={exporting}>
              <Download size={16} /> {exporting ? t("budgetsExporting") : t("budgetsExportJson")}
            </Button>
          </div>
        ) : null}
      </div>
      {error && (
        <ApiNotice
          title={t("budgetsBudgetLedgerUnavailable")}
          message={error}
          action={<Button onClick={onRetry}>{t("commonRetry")}</Button>}
        />
      )}
      <table className="data-table compact-table">
        <thead>
          <tr>
            <th>{t("budgetsEvent")}</th>
            <th>{t("budgetsScope")}</th>
            <th>{t("budgetsEstimated")}</th>
            <th>{t("budgetsActual")}</th>
            <th>{t("budgetsReason")}</th>
            <th>{t("budgetsRequest")}</th>
          </tr>
        </thead>
        <tbody>
          {loading && (
            <tr>
              <td colSpan={6}>{t("budgetsLoadingBudgetLedger")}</td>
            </tr>
          )}
          {!loading && !items.length && (
            <tr>
              <td colSpan={6}>{t("budgetsNoBudgetLedger")}</td>
            </tr>
          )}
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <StatusBadge status={item.event_type} label={eventLabel(item.event_type, t)} />
                <span className="row-subtitle">{formatDateTime(item.created_at, locale)}</span>
              </td>
              <td>
                {budgetLedgerScopeLabel(item, t)}
                {item.budget_id && <span className="row-subtitle">{shortId(item.budget_id)}</span>}
              </td>
              <td>
                {formatNumber(item.estimated_tokens, {}, locale)}
                <span className="row-subtitle">{formatCurrency(item.estimated_cost_amount, item.currency)}</span>
              </td>
              <td>
                {formatNumber(item.actual_tokens, {}, locale)}
                <span className="row-subtitle">{formatCurrency(item.actual_cost_amount, item.currency)}</span>
              </td>
              <td>{item.reason ?? t("budgetsNoReason")}</td>
              <td>
                <code>{shortId(item.request_id)}</code>
                <span className="row-subtitle">{shortId(item.reservation_id)}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function eventLabel(eventType: BudgetLedgerItem["event_type"], t: (key: string) => string) {
  if (eventType === "settle") {
    return t("budgetsEventSettle");
  }
  if (eventType === "release") {
    return t("budgetsEventRelease");
  }
  if (eventType === "deny") {
    return t("budgetsEventDeny");
  }
  if (eventType === "alert") {
    return t("budgetsEventAlert");
  }
  return t("budgetsEventReserve");
}

function budgetLedgerScopeLabel(item: BudgetLedgerItem, t: (key: string) => string) {
  if (item.scope_id) {
    return `${scopeLabel(item.scope_type, t)} ${shortId(item.scope_id)}`;
  }
  return scopeLabel(item.scope_type, t);
}

function scopeLabel(scopeType: BudgetLedgerItem["scope_type"], t: (key: string) => string) {
  const suffix = scopeType
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
  return t(`budgetsScope${suffix}`);
}

function shortId(value: string) {
  if (value.startsWith("proto-") || value.startsWith("reserve-") || value.startsWith("alert-")) {
    return value;
  }
  return value.slice(0, 8);
}
