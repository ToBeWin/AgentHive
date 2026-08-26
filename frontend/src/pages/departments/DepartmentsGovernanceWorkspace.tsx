import { PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type {
  CostCenterResponse,
  CostCenterUpdateRequest,
  DepartmentResponse,
  DepartmentUpdateRequest,
  RoleResponse,
} from "../../lib/api";
import type { DepartmentsGovernanceTab } from "./departmentsWorkspaceTypes";
import { OrgGovernancePanel } from "./OrgGovernancePanel";
import { OrgReferencePanels } from "./OrgReferencePanels";

interface DepartmentsGovernanceWorkspaceProps {
  activeTab: DepartmentsGovernanceTab;
  costCenters: CostCenterResponse[];
  costCentersLoading: boolean;
  deletingRoleId: string | null;
  departments: DepartmentResponse[];
  onDeleteCostCenter: (costCenterId: string) => Promise<boolean>;
  onDeleteDepartment: (departmentId: string) => Promise<boolean>;
  onDeleteRole: (roleId: string) => Promise<boolean>;
  onTabChange: (tab: DepartmentsGovernanceTab) => void;
  onUpdateCostCenter: (costCenterId: string, payload: CostCenterUpdateRequest) => Promise<boolean>;
  onUpdateDepartment: (departmentId: string, payload: DepartmentUpdateRequest) => Promise<boolean>;
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
  saving: boolean;
  selectedDepartment: DepartmentResponse | null;
  updatingRoleId: string | null;
}

export function DepartmentsGovernanceWorkspace({
  activeTab,
  costCenters,
  costCentersLoading,
  deletingRoleId,
  departments,
  onDeleteCostCenter,
  onDeleteDepartment,
  onDeleteRole,
  onTabChange,
  onUpdateCostCenter,
  onUpdateDepartment,
  onUpdateRole,
  roles,
  rolesLoading,
  saving,
  selectedDepartment,
  updatingRoleId,
}: DepartmentsGovernanceWorkspaceProps) {
  const { t } = useLocale();

  return (
    <div className="nested-workspace">
      <PageTabs
        active={activeTab}
        onChange={onTabChange}
        tabs={[
          {
            id: "department",
            label: t("departmentsGovernanceTabDepartment"),
            description: t("departmentsGovernanceTabDepartmentDesc"),
          },
          {
            id: "roles",
            label: t("departmentsGovernanceTabRoles"),
            description: t("departmentsGovernanceTabRolesDesc"),
          },
          {
            id: "costs",
            label: t("departmentsGovernanceTabCosts"),
            description: t("departmentsGovernanceTabCostsDesc"),
          },
        ]}
      />
      {activeTab === "department" && (
        <OrgGovernancePanel
          costCenters={costCenters}
          departments={departments}
          onDeleteCostCenter={onDeleteCostCenter}
          onDeleteDepartment={onDeleteDepartment}
          onUpdateCostCenter={onUpdateCostCenter}
          onUpdateDepartment={onUpdateDepartment}
          saving={saving}
          selectedDepartment={selectedDepartment}
        />
      )}
      {activeTab === "roles" && (
        <OrgReferencePanels
          costCenters={costCenters}
          costCentersLoading={costCentersLoading}
          deletingRoleId={deletingRoleId}
          departments={departments}
          mode="roles"
          onDeleteRole={onDeleteRole}
          onUpdateRole={onUpdateRole}
          roles={roles}
          rolesLoading={rolesLoading}
          updatingRoleId={updatingRoleId}
        />
      )}
      {activeTab === "costs" && (
        <OrgReferencePanels
          costCenters={costCenters}
          costCentersLoading={costCentersLoading}
          deletingRoleId={deletingRoleId}
          departments={departments}
          mode="costs"
          onDeleteRole={onDeleteRole}
          onUpdateRole={onUpdateRole}
          roles={roles}
          rolesLoading={rolesLoading}
          updatingRoleId={updatingRoleId}
        />
      )}
    </div>
  );
}
