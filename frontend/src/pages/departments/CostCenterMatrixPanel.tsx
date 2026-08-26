import { LoadingState, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { CostCenterResponse, DepartmentResponse } from "../../lib/api";
import { formatCurrency } from "../../lib/formatters";

interface CostCenterMatrixPanelProps {
  costCenters: CostCenterResponse[];
  departments: DepartmentResponse[];
  loading: boolean;
}

export function CostCenterMatrixPanel({ costCenters, departments, loading }: CostCenterMatrixPanelProps) {
  const { t } = useLocale();
  const departmentNames = new Map(departments.map((department) => [department.id, department.name]));

  return (
    <section className="mini-panel cost-center-matrix">
      <div className="panel-title compact">
        <h3>{t("departmentsCostCenterMatrix")}</h3>
        <span>
          {costCenters.length} {t("departmentsCostCentersCount")}
        </span>
      </div>
      <div className="table-scroll">
        <table className="data-table compact-table">
          <thead>
            <tr>
              <th>{t("departmentsCostCenterCode")}</th>
              <th>{t("departmentsCostCenterName")}</th>
              <th>{t("departmentsDepartmentColumn")}</th>
              <th>{t("departmentsMonthlyBudget")}</th>
              <th>{t("departmentsStatus")}</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5}>
                  <LoadingState lines={3} />
                </td>
              </tr>
            )}
            {!loading && !costCenters.length && (
              <tr>
                <td colSpan={5}>{t("departmentsNoCostCenters")}</td>
              </tr>
            )}
            {costCenters.map((costCenter) => (
              <tr key={costCenter.id}>
                <td>
                  <code>{costCenter.code}</code>
                </td>
                <td>
                  <strong>{costCenter.name}</strong>
                  {costCenter.description && <span className="row-subtitle">{costCenter.description}</span>}
                </td>
                <td>{departmentLabel(costCenter, departmentNames, t("departmentsTenantWide"))}</td>
                <td>{formatCurrency(costCenter.monthly_budget_usd ?? "0")}</td>
                <td>
                  <StatusBadge
                    label={costCenter.is_active ? t("departmentsCostCenterActive") : t("departmentsCostCenterInactive")}
                    status={costCenter.is_active ? "ACTIVE" : "DISABLED"}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function departmentLabel(
  costCenter: CostCenterResponse,
  departmentNames: Map<string, string>,
  tenantWideLabel: string,
) {
  if (!costCenter.department_id) {
    return tenantWideLabel;
  }
  return departmentNames.get(costCenter.department_id) ?? costCenter.department_id.slice(0, 8);
}
