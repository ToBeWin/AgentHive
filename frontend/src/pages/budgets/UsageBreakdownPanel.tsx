import { ApiNotice, Button, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { UsageBreakdownDimension, UsageBreakdownItem, UsageBreakdownResponse } from "../../lib/api";
import { formatCurrency, formatDateTime, formatNumber } from "../../lib/formatters";

const BREAKDOWN_DIMENSIONS: UsageBreakdownDimension[] = [
  "department",
  "user",
  "cost_center",
  "agent",
  "channel",
  "model",
  "status",
];

export function UsageBreakdownPanel({
  breakdown,
  dimension,
  error,
  loading,
  onDimensionChange,
  onRetry,
}: {
  breakdown: UsageBreakdownResponse | null;
  dimension: UsageBreakdownDimension;
  error: string | null;
  loading: boolean;
  onDimensionChange: (dimension: UsageBreakdownDimension) => void;
  onRetry: () => void;
}) {
  const { locale, t } = useLocale();
  const items = breakdown?.items ?? [];
  const maxCost = Math.max(...items.map((item) => Number(item.cost_amount)), 0);

  return (
    <section className="panel">
      <div className="panel-title-row budget-breakdown-title">
        <div>
          <h2>{t("budgetsUsageBreakdown")}</h2>
          <p>{t("budgetsUsageBreakdownSubtitle")}</p>
        </div>
      </div>
      <fieldset className="segmented compact-segmented">
        <legend>{t("budgetsBreakdownDimension")}</legend>
        {BREAKDOWN_DIMENSIONS.map((item) => (
          <button
            className={dimension === item ? "active" : undefined}
            key={item}
            type="button"
            onClick={() => onDimensionChange(item)}
          >
            {breakdownDimensionLabel(item, t)}
          </button>
        ))}
      </fieldset>
      {error && (
        <ApiNotice
          title={t("budgetsUsageBreakdownUnavailable")}
          message={error}
          action={<Button onClick={onRetry}>{t("commonRetry")}</Button>}
        />
      )}
      <table className="data-table compact-table">
        <thead>
          <tr>
            <th>{t("budgetsBreakdownDimension")}</th>
            <th>{t("overviewCostColumn")}</th>
            <th>{t("overviewTokenColumn")}</th>
            <th>{t("budgetsRequests")}</th>
            <th>{t("budgetsLastUsed")}</th>
          </tr>
        </thead>
        <tbody>
          {loading && (
            <tr>
              <td colSpan={5}>{t("budgetsLoadingBreakdown")}</td>
            </tr>
          )}
          {!loading && !items.length && (
            <tr>
              <td colSpan={5}>{t("budgetsNoBreakdown")}</td>
            </tr>
          )}
          {items.map((item) => (
            <tr key={`${item.dimension}:${item.key}`}>
              <td>
                <strong>{breakdownLabel(item, t)}</strong>
                <span className="row-subtitle">
                  {t("budgetsSuccessFailure")
                    .replace("{{success}}", String(item.success_count))
                    .replace("{{error}}", String(item.error_count))}
                </span>
              </td>
              <td>
                <span>{formatCurrency(item.cost_amount, item.currency)}</span>
                <div className="mini-bar">
                  <span style={{ width: `${barWidth(item.cost_amount, maxCost)}%` }} />
                </div>
              </td>
              <td>{formatNumber(item.total_tokens, {}, locale)}</td>
              <td>
                <StatusBadge status={String(item.request_count)} />
              </td>
              <td>{item.last_used_at ? formatDateTime(item.last_used_at, locale) : t("budgetsNotUsed")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function breakdownLabel(item: UsageBreakdownItem, t: (key: string) => string) {
  if (item.key === "unassigned") {
    return t("budgetsUnassigned");
  }
  if (item.dimension === "model" || item.dimension === "status") {
    return item.key;
  }
  return item.label ?? item.key.slice(0, 8);
}

function breakdownDimensionLabel(dimension: UsageBreakdownDimension, t: (key: string) => string) {
  const labels: Record<UsageBreakdownDimension, string> = {
    agent: t("budgetsBreakdownAgent"),
    channel: t("budgetsBreakdownChannel"),
    cost_center: t("budgetsBreakdownCostCenter"),
    department: t("budgetsBreakdownDepartment"),
    model: t("budgetsBreakdownModel"),
    status: t("budgetsBreakdownStatus"),
    user: t("budgetsBreakdownUser"),
  };
  return labels[dimension];
}

function barWidth(value: string, maxCost: number) {
  if (maxCost <= 0) {
    return 0;
  }
  return Math.max(4, Math.min(100, (Number(value) / maxCost) * 100));
}
