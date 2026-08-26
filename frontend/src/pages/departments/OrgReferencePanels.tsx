import { useLocale } from "../../i18n-context";
import type { CostCenterResponse, DepartmentResponse, RoleResponse } from "../../lib/api";
import { formatCurrency } from "../../lib/formatters";
import { CostCenterMatrixPanel } from "./CostCenterMatrixPanel";
import { RoleManagementPanel } from "./RoleManagementPanel";

type OrgReferenceMode = "all" | "roles" | "costs";

export function OrgReferencePanels({
  costCenters,
  costCentersLoading,
  deletingRoleId,
  departments,
  mode = "all",
  onDeleteRole,
  onUpdateRole,
  roles,
  rolesLoading,
  updatingRoleId,
}: {
  costCenters: CostCenterResponse[];
  costCentersLoading: boolean;
  deletingRoleId: string | null;
  departments: DepartmentResponse[];
  mode?: OrgReferenceMode;
  onDeleteRole: (roleId: string) => Promise<boolean>;
  onUpdateRole: (
    roleId: string,
    form: {
      description: string;
      name: string;
      permissions: string;
    },
  ) => Promise<boolean>;
  roles: RoleResponse[];
  rolesLoading: boolean;
  updatingRoleId: string | null;
}) {
  const { t } = useLocale();
  const rolePanel = (
    <RoleManagementPanel
      deletingRoleId={deletingRoleId}
      loading={rolesLoading}
      onDeleteRole={onDeleteRole}
      onUpdateRole={onUpdateRole}
      roles={roles}
      updatingRoleId={updatingRoleId}
    />
  );
  const costSummaryPanel = (
    <section className="mini-panel">
      <h3>{t("departmentsCostCenters")}</h3>
      {costCentersLoading && <span>{t("departmentsLoadingCostCenters")}</span>}
      {!costCentersLoading && !costCenters.length && <span>{t("departmentsNoCostCenters")}</span>}
      {costCenters.slice(0, 4).map((costCenter) => (
        <div className="org-list-row" key={costCenter.id}>
          <strong>{costCenter.code}</strong>
          <span>
            {formatCurrency(costCenter.monthly_budget_usd ?? "0")}
            {t("departmentsPerMonth")}
          </span>
        </div>
      ))}
    </section>
  );

  if (mode === "roles") {
    return rolePanel;
  }

  if (mode === "costs") {
    return (
      <>
        {costSummaryPanel}
        <CostCenterMatrixPanel costCenters={costCenters} departments={departments} loading={costCentersLoading} />
      </>
    );
  }

  return (
    <>
      <div className="grid two lower">
        {rolePanel}
        {costSummaryPanel}
      </div>
      <CostCenterMatrixPanel costCenters={costCenters} departments={departments} loading={costCentersLoading} />
    </>
  );
}
