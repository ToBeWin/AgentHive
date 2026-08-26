import { Plus } from "lucide-react";
import { ApiNotice, Button, PageHeader, PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type {
  CostCenterResponse,
  CostCenterUpdateRequest,
  DepartmentResponse,
  DepartmentTreeNode,
  DepartmentUpdateRequest,
  PermissionCatalogItem,
  RolePresetItem,
  RoleResponse,
  UserResponse,
  UserUpdateRequest,
} from "../../lib/api";
import { DepartmentsGovernanceWorkspace } from "./DepartmentsGovernanceWorkspace";
import { DepartmentsPeopleWorkspace } from "./DepartmentsPeopleWorkspace";
import { DepartmentsSetupWorkspace } from "./DepartmentsSetupWorkspace";
import { DepartmentTreeSidebar } from "./DepartmentTreeSidebar";
import type { DepartmentsGovernanceTab, DepartmentsPageTab } from "./departmentsWorkspaceTypes";
import type { CostCenterFormState, DepartmentFormState, RoleFormState, UserFormState } from "./departmentUtils";
import { OrgGovernanceLoopPanel } from "./OrgGovernanceLoopPanel";
import type { OrgSetupTab } from "./OrgQuickActionsPanel";

export type { DepartmentsGovernanceTab, DepartmentsPageTab } from "./departmentsWorkspaceTypes";

interface DepartmentsWorkspaceProps {
  actionError: string | null;
  actionMessage: string | null;
  activeTab: DepartmentsPageTab;
  costCenterForm: CostCenterFormState;
  costCenterList: CostCenterResponse[];
  costCentersError: string | null;
  costCentersLoading: boolean;
  departmentForm: DepartmentFormState;
  departments: DepartmentResponse[];
  departmentsError: string | null;
  departmentsLoading: boolean;
  governanceTab: DepartmentsGovernanceTab;
  onCreateCostCenter: () => void;
  onCreateDepartment: () => void;
  onCreateRole: () => void;
  onCreateUser: () => void;
  onCostCenterFormChange: (form: CostCenterFormState) => void;
  onDeleteCostCenter: (costCenterId: string) => Promise<boolean>;
  onDeleteDepartment: (departmentId: string) => Promise<boolean>;
  onDeleteRole: (roleId: string) => Promise<boolean>;
  onDepartmentFormChange: (form: DepartmentFormState) => void;
  onGovernanceTabChange: (tab: DepartmentsGovernanceTab) => void;
  onPrimaryDepartmentAction: () => void;
  onPrimaryUserAction: () => void;
  onRefetchDepartments: () => void;
  onRefreshOrg: () => void;
  onResetUserPassword: (userId: string, password: string) => Promise<boolean>;
  onRoleFormChange: (form: RoleFormState) => void;
  onSelectDepartment: (departmentId: string) => void;
  onSetupTabChange: (tab: OrgSetupTab) => void;
  onTabChange: (tab: DepartmentsPageTab) => void;
  onToggleUserStatus: (userId: string, isActive: boolean) => void;
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
  onUpdateUser: (userId: string, payload: UserUpdateRequest) => Promise<boolean>;
  onUserFormChange: (form: UserFormState) => void;
  passwordResettingUserId: string | null;
  roleDeletingId: string | null;
  roleForm: RoleFormState;
  roleList: RoleResponse[];
  rolePermissions: PermissionCatalogItem[];
  rolePermissionsError: string | null;
  rolePermissionsLoading: boolean;
  rolePresets: RolePresetItem[];
  rolePresetsError: string | null;
  rolePresetsLoading: boolean;
  roleUpdatingId: string | null;
  rolesError: string | null;
  rolesLoading: boolean;
  saving: boolean;
  selectableCostCenters: CostCenterResponse[];
  selectedDepartment: DepartmentResponse | null;
  setupTab: OrgSetupTab;
  statusUpdatingUserId: string | null;
  tree: DepartmentTreeNode[];
  userForm: UserFormState;
  userList: UserResponse[];
  userUpdatingId: string | null;
  usersError: string | null;
  usersLoading: boolean;
  visibleUsers: UserResponse[];
  showDiagnostics?: boolean;
}

export function DepartmentsWorkspace({
  actionError,
  actionMessage,
  activeTab,
  costCenterForm,
  costCenterList,
  costCentersError,
  costCentersLoading,
  departmentForm,
  departments,
  departmentsError,
  departmentsLoading,
  governanceTab,
  onCreateCostCenter,
  onCreateDepartment,
  onCreateRole,
  onCreateUser,
  onCostCenterFormChange,
  onDeleteCostCenter,
  onDeleteDepartment,
  onDeleteRole,
  onDepartmentFormChange,
  onGovernanceTabChange,
  onPrimaryDepartmentAction,
  onPrimaryUserAction,
  onRefetchDepartments,
  onRefreshOrg,
  onResetUserPassword,
  onRoleFormChange,
  onSelectDepartment,
  onSetupTabChange,
  onTabChange,
  onToggleUserStatus,
  onUpdateCostCenter,
  onUpdateDepartment,
  onUpdateRole,
  onUpdateUser,
  onUserFormChange,
  passwordResettingUserId,
  roleDeletingId,
  roleForm,
  roleList,
  rolePermissions,
  rolePermissionsError,
  rolePermissionsLoading,
  rolePresets,
  rolePresetsError,
  rolePresetsLoading,
  roleUpdatingId,
  rolesError,
  rolesLoading,
  saving,
  selectableCostCenters,
  selectedDepartment,
  setupTab,
  statusUpdatingUserId,
  tree,
  userForm,
  userList,
  userUpdatingId,
  usersError,
  usersLoading,
  visibleUsers,
  showDiagnostics = false,
}: DepartmentsWorkspaceProps) {
  const { t } = useLocale();
  const orgError = usersError ?? rolesError ?? costCentersError ?? rolePermissionsError ?? rolePresetsError;

  return (
    <section className="page split-admin">
      <DepartmentTreeSidebar
        costCenterCount={costCenterList.length}
        departments={departments}
        error={departmentsError}
        loading={departmentsLoading}
        onRetry={onRefetchDepartments}
        onSelect={onSelectDepartment}
        roleCount={roleList.length}
        selectedDepartment={selectedDepartment}
        tree={tree}
      />
      <section className="panel">
        <PageHeader
          title={
            selectedDepartment
              ? t("departmentsUsersTitle").replace("{{department}}", selectedDepartment.name)
              : t("departmentsTitle")
          }
          subtitle={t("departmentsSubtitle")}
          actions={
            <>
              <Button
                onClick={onPrimaryDepartmentAction}
                disabled={activeTab === "setup" && (saving || !departmentForm.name.trim())}
              >
                <Plus size={16} /> {t("departmentsAddDepartment")}
              </Button>
              <Button
                variant="primary"
                onClick={onPrimaryUserAction}
                disabled={activeTab === "setup" && (saving || !userForm.email.trim() || userForm.password.length < 8)}
              >
                <Plus size={16} /> {t("departmentsAddUser")}
              </Button>
            </>
          }
        />
        {orgError && (
          <ApiNotice
            title={t("departmentsOrgApiNotice")}
            message={orgError ?? t("departmentsOrgApiFallback")}
            action={<Button onClick={onRefreshOrg}>{t("commonRetry")}</Button>}
          />
        )}
        {showDiagnostics ? (
          <OrgGovernanceLoopPanel
            activeTab={activeTab}
            costCenters={costCenterList}
            departments={departments}
            governanceTab={governanceTab}
            onOpenCostGovernance={() => {
              onTabChange("governance");
              onGovernanceTabChange("costs");
            }}
            onOpenDepartmentGovernance={() => {
              onTabChange("governance");
              onGovernanceTabChange("department");
            }}
            onOpenPeople={() => onTabChange("people")}
            onOpenRoleSetup={() => {
              onTabChange("setup");
              onSetupTabChange("role");
            }}
            onOpenUserSetup={() => {
              onTabChange("setup");
              onSetupTabChange("user");
            }}
            rolePermissions={rolePermissions}
            roles={roleList}
            selectedDepartment={selectedDepartment}
            setupTab={setupTab}
            users={userList}
          />
        ) : null}
        <PageTabs
          active={activeTab}
          onChange={onTabChange}
          tabs={[
            { id: "people", label: t("departmentsTabPeople"), description: t("departmentsTabPeopleDesc") },
            { id: "setup", label: t("departmentsTabSetup"), description: t("departmentsTabSetupDesc") },
            { id: "governance", label: t("departmentsTabGovernance"), description: t("departmentsTabGovernanceDesc") },
          ]}
        />
        {activeTab === "people" && (
          <DepartmentsPeopleWorkspace
            costCenters={costCenterList}
            departments={departments}
            loading={usersLoading}
            onResetUserPassword={onResetUserPassword}
            onToggleUserStatus={onToggleUserStatus}
            onUpdateUser={onUpdateUser}
            passwordResettingUserId={passwordResettingUserId}
            roles={roleList}
            selectedDepartment={selectedDepartment}
            statusUpdatingUserId={statusUpdatingUserId}
            updatingUserId={userUpdatingId}
            users={visibleUsers}
          />
        )}
        {activeTab === "setup" && (
          <DepartmentsSetupWorkspace
            actionError={actionError}
            actionMessage={actionMessage}
            activeTab={setupTab}
            costCenterForm={costCenterForm}
            departmentForm={departmentForm}
            onCreateDepartment={onCreateDepartment}
            onCostCenterFormChange={onCostCenterFormChange}
            onCreateCostCenter={onCreateCostCenter}
            onCreateRole={onCreateRole}
            onCreateUser={onCreateUser}
            onDepartmentFormChange={onDepartmentFormChange}
            onRoleFormChange={onRoleFormChange}
            onTabChange={onSetupTabChange}
            onUserFormChange={onUserFormChange}
            rolePermissions={rolePermissions}
            rolePermissionsLoading={rolePermissionsLoading}
            roleForm={roleForm}
            rolePresets={rolePresets}
            rolePresetsLoading={rolePresetsLoading}
            roles={roleList}
            selectableCostCenters={selectableCostCenters}
            saving={saving}
            userForm={userForm}
          />
        )}
        {activeTab === "governance" && (
          <DepartmentsGovernanceWorkspace
            activeTab={governanceTab}
            costCenters={costCenterList}
            costCentersLoading={costCentersLoading}
            deletingRoleId={roleDeletingId}
            departments={departments}
            onDeleteCostCenter={onDeleteCostCenter}
            onDeleteDepartment={onDeleteDepartment}
            onDeleteRole={onDeleteRole}
            onTabChange={onGovernanceTabChange}
            onUpdateCostCenter={onUpdateCostCenter}
            onUpdateDepartment={onUpdateDepartment}
            onUpdateRole={onUpdateRole}
            roles={roleList}
            rolesLoading={rolesLoading}
            saving={saving}
            selectedDepartment={selectedDepartment}
            updatingRoleId={roleUpdatingId}
          />
        )}
      </section>
    </section>
  );
}
