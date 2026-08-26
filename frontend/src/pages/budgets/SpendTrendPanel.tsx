import { ApiNotice, Button } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import { decimalToNumber, formatCurrency, formatNumber } from "../../lib/formatters";

export function SpendTrendPanel({
  currency,
  loading,
  onRetry,
  periodLabel,
  storageUnavailable,
  summaryError,
  totalLimit,
  totalPct,
  totalSpent,
  totalTokens,
}: {
  currency: string;
  loading: boolean;
  onRetry: () => void;
  periodLabel: string;
  storageUnavailable: boolean;
  summaryError: string | null;
  totalLimit: string;
  totalPct: number;
  totalSpent: string;
  totalTokens: number;
}) {
  const { locale, t } = useLocale();
  const hasSpend = decimalToNumber(totalSpent) > 0;
  const spendLinePath = hasSpend
    ? "M0 205 C80 160 160 200 240 155 C330 100 370 80 455 110 C565 155 620 95 720 52"
    : "M0 218 L720 218";
  const spendAreaPath = hasSpend
    ? "M0 205 C80 160 160 200 240 155 C330 100 370 80 455 110 C565 155 620 95 720 52 L720 260 L0 260 Z"
    : "M0 218 L720 218 L720 260 L0 260 Z";

  return (
    <section className="panel">
      <div className="panel-title">
        <h2>{t("budgetsSpendTrend")}</h2>
        <strong className="big-money">
          {loading ? t("budgetsLoading") : formatCurrency(totalSpent, currency)} <span>/ {periodLabel}</span>
        </strong>
      </div>
      {summaryError && (
        <ApiNotice
          title={t("budgetsSummaryUnavailable")}
          message={summaryError}
          action={<Button onClick={onRetry}>{t("commonRetry")}</Button>}
        />
      )}
      {storageUnavailable && <div className="inline-note">{t("budgetsStorageUnavailable")}</div>}
      <div className="area-chart">
        <svg viewBox="0 0 720 260" role="img" aria-labelledby="spend-chart-title">
          <title id="spend-chart-title">{t("budgetsMonthlySpendChart")}</title>
          <defs>
            <linearGradient id="spend" x1="0" x2="0" y1="0" y2="1">
              <stop stopColor="#008378" stopOpacity=".24" />
              <stop offset="1" stopColor="#008378" stopOpacity=".08" />
            </linearGradient>
          </defs>
          <path d={spendAreaPath} fill="url(#spend)" />
          <path d={spendLinePath} fill="none" stroke="#008378" strokeWidth="3" />
        </svg>
      </div>
      <div className="budget-summary-row">
        <div>
          <span>{t("budgetsTotalLimit")}</span>
          <strong>{formatCurrency(totalLimit, currency)}</strong>
        </div>
        <div>
          <span>{t("budgetsTokenUsage")}</span>
          <strong>{formatNumber(totalTokens, {}, locale)}</strong>
        </div>
        <div>
          <span>{t("budgetsLimitUsed")}</span>
          <strong>{totalPct}%</strong>
        </div>
      </div>
    </section>
  );
}
