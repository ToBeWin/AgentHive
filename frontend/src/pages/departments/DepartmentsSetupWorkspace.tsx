import type { CostCenterResponse, PermissionCatalogItem, RolePresetItem, RoleResponse } from "../../lib/api";
import type { CostCenterFormState, DepartmentFormState, RoleFormState, UserFormState } from "./departmentUtils";
import { OrgQuickActionsPanel, type OrgSetupTab } from "./OrgQuickActionsPanel";

interface DepartmentsSetupWorkspaceProps {
  actionError: string | null;
  actionMessage: string | null;
  activeTab: OrgSetupTab;
  costCenterForm: CostCenterFormState;
  departmentForm: DepartmentFormState;
  onCreateCostCenter: () => void;
  onCreateDepartment: () => void;
  onCreateRole: () => void;
  onCreateUser: () => void;
  onCostCenterFormChange: (form: CostCenterFormState) => void;
  onDepartmentFormChange: (form: DepartmentFormState) => void;
  onRoleFormChange: (form: RoleFormState) => void;
  onTabChange: (tab: OrgSetupTab) => void;
  onUserFormChange: (form: UserFormState) => void;
  roleForm: RoleFormState;
  rolePermissions: PermissionCatalogItem[];
  rolePermissionsLoading: boolean;
  rolePresets: RolePresetItem[];
  rolePresetsLoading: boolean;
  roles: RoleResponse[];
  saving: boolean;
  selectableCostCenters: CostCenterResponse[];
  userForm: UserFormState;
}

export function DepartmentsSetupWorkspace(props: DepartmentsSetupWorkspaceProps) {
  return <OrgQuickActionsPanel {...props} />;
}
