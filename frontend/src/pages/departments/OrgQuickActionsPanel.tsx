import { cx, PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { CostCenterResponse, PermissionCatalogItem, RolePresetItem, RoleResponse } from "../../lib/api";
import { CostCenterQuickCreatePanel } from "./CostCenterQuickCreatePanel";
import { DepartmentQuickCreatePanel } from "./DepartmentQuickCreatePanel";
import type { CostCenterFormState, DepartmentFormState, RoleFormState, UserFormState } from "./departmentUtils";
import type { OrgSetupTab } from "./orgSetupTypes";
import { RoleQuickCreatePanel } from "./RoleQuickCreatePanel";
import { UserQuickCreatePanel } from "./UserQuickCreatePanel";

export type { OrgSetupTab } from "./orgSetupTypes";

export function OrgQuickActionsPanel({
  actionError,
  actionMessage,
  activeTab,
  costCenterForm,
  departmentForm,
  onCreateDepartment,
  onCostCenterFormChange,
  onCreateCostCenter,
  onCreateRole,
  onCreateUser,
  onDepartmentFormChange,
  onRoleFormChange,
  onTabChange,
  onUserFormChange,
  roles,
  rolePermissions,
  rolePermissionsLoading,
  roleForm,
  rolePresets,
  rolePresetsLoading,
  selectableCostCenters,
  saving,
  userForm,
}: {
  actionError: string | null;
  actionMessage: string | null;
  activeTab: OrgSetupTab;
  costCenterForm: CostCenterFormState;
  departmentForm: DepartmentFormState;
  onCreateDepartment: () => void;
  onCostCenterFormChange: (form: CostCenterFormState) => void;
  onCreateCostCenter: () => void;
  onCreateRole: () => void;
  onCreateUser: () => void;
  onDepartmentFormChange: (form: DepartmentFormState) => void;
  onRoleFormChange: (form: RoleFormState) => void;
  onTabChange: (tab: OrgSetupTab) => void;
  onUserFormChange: (form: UserFormState) => void;
  roles: RoleResponse[];
  rolePermissions: PermissionCatalogItem[];
  rolePermissionsLoading: boolean;
  roleForm: RoleFormState;
  rolePresets: RolePresetItem[];
  rolePresetsLoading: boolean;
  selectableCostCenters: CostCenterResponse[];
  saving: boolean;
  userForm: UserFormState;
}) {
  const { t } = useLocale();

  return (
    <>
      {(actionMessage || actionError) && (
        <div className={cx("form-message", actionError ? "error" : false)}>{actionError ?? actionMessage}</div>
      )}
      <PageTabs
        active={activeTab}
        onChange={onTabChange}
        tabs={[
          {
            id: "department",
            label: t("departmentsSetupTabDepartment"),
            description: t("departmentsSetupTabDepartmentDesc"),
          },
          { id: "user", label: t("departmentsSetupTabUser"), description: t("departmentsSetupTabUserDesc") },
          { id: "role", label: t("departmentsSetupTabRole"), description: t("departmentsSetupTabRoleDesc") },
          { id: "cost", label: t("departmentsSetupTabCost"), description: t("departmentsSetupTabCostDesc") },
        ]}
      />
      {activeTab === "department" && (
        <DepartmentQuickCreatePanel
          departmentForm={departmentForm}
          onCreateDepartment={onCreateDepartment}
          onDepartmentFormChange={onDepartmentFormChange}
          saving={saving}
        />
      )}
      {activeTab === "user" && (
        <UserQuickCreatePanel
          onCreateUser={onCreateUser}
          onUserFormChange={onUserFormChange}
          roles={roles}
          saving={saving}
          selectableCostCenters={selectableCostCenters}
          userForm={userForm}
        />
      )}
      {activeTab === "role" && (
        <RoleQuickCreatePanel
          onCreateRole={onCreateRole}
          onRoleFormChange={onRoleFormChange}
          roleForm={roleForm}
          rolePermissions={rolePermissions}
          rolePermissionsLoading={rolePermissionsLoading}
          rolePresets={rolePresets}
          rolePresetsLoading={rolePresetsLoading}
          saving={saving}
        />
      )}
      {activeTab === "cost" && (
        <CostCenterQuickCreatePanel
          costCenterForm={costCenterForm}
          onCostCenterFormChange={onCostCenterFormChange}
          onCreateCostCenter={onCreateCostCenter}
          saving={saving}
        />
      )}
    </>
  );
}
