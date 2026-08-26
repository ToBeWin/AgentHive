import { useLocale } from "../../i18n-context";
import type {
  BudgetPeriod,
  BudgetSummaryResponse,
  UsageBreakdownDimension,
  UsageBreakdownResponse,
} from "../../lib/api";
import { budgetUsagePct } from "../../lib/formatters";
import { BudgetGovernancePanel, ScopeUtilizationPanel, SpendTrendPanel, UsageBreakdownPanel } from "./BudgetPanels";

interface BudgetOverviewWorkspaceProps {
  breakdown: UsageBreakdownResponse | null;
  breakdownDimension: UsageBreakdownDimension;
  breakdownError: string | null;
  breakdownLoading: boolean;
  onBreakdownDimensionChange: (dimension: UsageBreakdownDimension) => void;
  onCreatePolicy: () => void;
  onRetryBreakdown: () => void;
  onRetrySummary: () => void;
  onSummaryPeriodChange: (period: BudgetPeriod) => void;
  periodLabel: string;
  summary: BudgetSummaryResponse | null;
  summaryError: string | null;
  summaryLoading: boolean;
  summaryPeriod: BudgetPeriod;
  totalLimit: string;
  totalSpent: string;
}

export function BudgetOverviewWorkspace({
  breakdown,
  breakdownDimension,
  breakdownError,
  breakdownLoading,
  onBreakdownDimensionChange,
  onCreatePolicy,
  onRetryBreakdown,
  onRetrySummary,
  onSummaryPeriodChange,
  periodLabel,
  summary,
  summaryError,
  summaryLoading,
  summaryPeriod,
  totalLimit,
  totalSpent,
}: BudgetOverviewWorkspaceProps) {
  const { t } = useLocale();

  return (
    <>
      <div className="segmented">
        <button
          type="button"
          className={summaryPeriod === "monthly" ? "active" : undefined}
          onClick={() => onSummaryPeriodChange("monthly")}
        >
          {t("budgetsMonthly")}
        </button>
        <button
          type="button"
          className={summaryPeriod === "daily" ? "active" : undefined}
          onClick={() => onSummaryPeriodChange("daily")}
        >
          {t("budgetsDaily")}
        </button>
      </div>
      <div className="budgets-overview-workspace budgets-overview-unified">
        <section className="budgets-overview-section">
          <header className="budgets-overview-section-head">
            <h2>{t("budgetsOverviewTabHealth")}</h2>
            <p>{t("budgetsOverviewTabHealthDesc")}</p>
          </header>
          <BudgetGovernancePanel loading={summaryLoading} summary={summary} />
          <SpendTrendPanel
            currency={summary?.currency ?? "USD"}
            loading={summaryLoading}
            periodLabel={periodLabel}
            storageUnavailable={summary?.metadata?.storage === "unavailable"}
            summaryError={summaryError}
            totalLimit={totalLimit}
            totalPct={budgetUsagePct(totalSpent, totalLimit)}
            totalSpent={totalSpent}
            totalTokens={summary?.total_tokens_used ?? 0}
            onRetry={onRetrySummary}
          />
        </section>
        <section className="budgets-overview-section" id="budget-attribution-section">
          <header className="budgets-overview-section-head">
            <h2>{t("budgetsOverviewTabAttribution")}</h2>
            <p>{t("budgetsOverviewTabAttributionDesc")}</p>
          </header>
          <UsageBreakdownPanel
            breakdown={breakdown}
            dimension={breakdownDimension}
            error={breakdownError}
            loading={breakdownLoading}
            onDimensionChange={onBreakdownDimensionChange}
            onRetry={onRetryBreakdown}
          />
          <ScopeUtilizationPanel
            loading={summaryLoading}
            onCreate={onCreatePolicy}
            rows={summary?.by_scope ?? []}
            warningCount={summary?.warning_policy_count ?? 0}
          />
        </section>
      </div>
    </>
  );
}
