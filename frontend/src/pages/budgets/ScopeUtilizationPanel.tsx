import { Button } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { BudgetScopeSummary } from "../../lib/api";
import { budgetUsagePct, formatCompactCurrency } from "../../lib/formatters";
import { formatScope } from "./budgetUtils";

export function ScopeUtilizationPanel({
  loading,
  onCreate,
  rows,
  warningCount,
}: {
  loading: boolean;
  onCreate?: () => void;
  rows: BudgetScopeSummary[];
  warningCount: number;
}) {
  const { t } = useLocale();
  return (
    <section className="panel">
      <h2>{t("budgetsScopeUtilization")}</h2>
      {renderScopeRows(rows, loading, t, onCreate)}
      {warningCount > 0 && (
        <div className="alert-box">
          {warningCount} {t("budgetsApproachingLimit")}
        </div>
      )}
    </section>
  );
}

function renderScopeRows(
  rows: BudgetScopeSummary[],
  loading: boolean,
  t: (key: string) => string,
  onCreate: (() => void) | undefined,
) {
  if (loading) {
    return <div className="budget-empty-state">{t("budgetsLoadingScopes")}</div>;
  }
  if (!rows.length) {
    return (
      <div className="budget-empty-state budget-empty-action">
        <span>{t("budgetsNoScopes")}</span>
        {onCreate && <Button onClick={onCreate}>{t("createBudget")}</Button>}
      </div>
    );
  }
  return rows.slice(0, 5).map((row) => {
    const pct = budgetUsagePct(row.amount_spent, row.amount_limit);
    const tone = pct >= 80 ? "danger" : "";
    return (
      <div className="bar-row" key={row.scope_type}>
        <div>
          <span>{formatScope(row.scope_type, t)}</span>
          <code className={tone}>
            {pct}% ({formatCompactCurrency(row.amount_spent)} / {formatCompactCurrency(row.amount_limit)})
          </code>
        </div>
        <div className="bar-track">
          <i className={tone} style={{ width: `${pct}%` }} />
        </div>
      </div>
    );
  });
}
