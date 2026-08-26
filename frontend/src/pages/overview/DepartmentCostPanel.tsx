import { ApiNotice } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { DepartmentUsageItem } from "../../lib/api";
import { formatCurrency } from "../../lib/formatters";

export function DepartmentCostPanel({
  departmentUsage,
  totalTokens,
}: {
  departmentUsage: DepartmentUsageItem[];
  totalTokens: number;
}) {
  const { t } = useLocale();

  return (
    <div className="grid one">
      <section className="panel">
        <h2>
          {t("overviewCostByDept")} <span>{t("overviewCostByDeptAlt")}</span>
        </h2>
        <div className="bars">
          {departmentUsage.length === 0 && (
            <ApiNotice title={t("overviewNoDepartmentCostTitle")} message={t("overviewNoDepartmentCostMessage")} />
          )}
          {departmentUsage.map((dept) => (
            <div className="bar-row" key={dept.department_id ?? dept.department_name}>
              <div>
                <span>{dept.department_name}</span>
                <code>{formatCurrency(dept.cost_usd)}</code>
              </div>
              <div className="bar-track">
                <i style={{ width: `${Math.min(100, (dept.tokens / Math.max(1, totalTokens)) * 100)}%` }} />
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
