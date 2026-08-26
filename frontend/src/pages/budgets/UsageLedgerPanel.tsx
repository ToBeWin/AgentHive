import { Download } from "lucide-react";
import { ApiNotice, Button, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { UsageLedgerItem } from "../../lib/api";
import { formatCurrency, formatNumber } from "../../lib/formatters";

export function UsageLedgerPanel({
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
  items: UsageLedgerItem[];
  loading: boolean;
  onExportCsv: () => void;
  onExportJson: () => void;
  onRetry: () => void;
}) {
  const { locale, t } = useLocale();
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>{t("budgetsRecentUsageLedger")}</h2>
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
          title={t("budgetsUsageLedgerUnavailable")}
          message={error}
          action={<Button onClick={onRetry}>{t("commonRetry")}</Button>}
        />
      )}
      <table className="data-table compact-table">
        <thead>
          <tr>
            <th>{t("budgetsModel")}</th>
            <th>{t("budgetsScope")}</th>
            <th>{t("overviewTokenColumn")}</th>
            <th>{t("overviewCostColumn")}</th>
            <th>{t("budgetsStatusError")}</th>
            <th>{t("budgetsRequest")}</th>
          </tr>
        </thead>
        <tbody>
          {loading && (
            <tr>
              <td colSpan={6}>{t("budgetsLoadingLedger")}</td>
            </tr>
          )}
          {!loading && !items.length && (
            <tr>
              <td colSpan={6}>{t("budgetsNoUsageLedger")}</td>
            </tr>
          )}
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <code>{item.model_key}</code>
                <span className="row-subtitle">
                  {String(item.metadata.provider_key ?? item.deployment_id ?? "no route")}
                </span>
              </td>
              <td>{ledgerScopeLabel(item, t)}</td>
              <td>{formatNumber(item.total_tokens, {}, locale)}</td>
              <td>{formatCurrency(item.cost_amount, item.currency)}</td>
              <td>
                <StatusBadge status={item.status} />
                {item.error_code && <span className="row-subtitle">{item.error_code}</span>}
              </td>
              <td>
                <code>{requestLabel(item.request_id)}</code>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function ledgerScopeLabel(item: UsageLedgerItem, t: (key: string) => string) {
  const scopes = [
    item.department_id ? `${t("budgetsScopeDepartment")} ${shortId(item.department_id)}` : null,
    item.user_id ? `${t("budgetsScopeUser")} ${shortId(item.user_id)}` : null,
    item.cost_center_id ? `${t("budgetsCostCenter")} ${shortId(item.cost_center_id)}` : null,
    item.agent_id ? `${t("budgetsScopeAgent")} ${shortId(item.agent_id)}` : null,
    item.channel_id ? `${t("budgetsScopeChannel")} ${shortId(item.channel_id)}` : null,
  ].filter(Boolean);
  return scopes.length ? scopes.join(" · ") : t("budgetsScopeTenant");
}

function shortId(value: string) {
  return value.slice(0, 8);
}

function requestLabel(value: string) {
  if (value.startsWith("proto-")) {
    return value;
  }
  return value.slice(0, 12);
}
