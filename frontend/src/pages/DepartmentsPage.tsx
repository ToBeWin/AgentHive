import type { WorkspaceId } from "../data";
import { showDeliveryDiagnostics } from "../lib/deliveryDiagnostics";
import { DepartmentsWorkspace } from "./departments/DepartmentsWorkspace";
import { useDepartmentsPageController } from "./departments/useDepartmentsPageController";

export function DepartmentsPage({
  activeWorkspace = "admin",
  isPrototype = false,
}: {
  activeWorkspace?: WorkspaceId;
  isPrototype?: boolean;
}) {
  const org = useDepartmentsPageController({ isPrototype });

  return (
    <DepartmentsWorkspace
      showDiagnostics={showDeliveryDiagnostics(activeWorkspace)}
      actionError={org.actionError}
      actionMessage={org.actionMessage}
      activeTab={org.activeTab}
      costCenterForm={org.costCenterForm}
      costCenterList={org.costCenterList}
      costCentersError={org.costCentersError}
      costCentersLoading={org.costCentersLoading}
      departmentForm={org.departmentForm}
      departments={org.departments}
      departmentsError={org.departmentsError}
      departmentsLoading={org.departmentsLoading}
      governanceTab={org.governanceTab}
      onCreateCostCenter={org.handleCreateCostCenter}
      onCreateDepartment={org.handleCreateDepartment}
      onCreateRole={org.handleCreateRole}
      onCreateUser={org.handleCreateUser}
      onCostCenterFormChange={org.setCostCenterForm}
      onDeleteCostCenter={org.handleDeleteCostCenter}
      onDeleteDepartment={org.handleDeleteDepartment}
      onDeleteRole={org.handleDeleteRole}
      onDepartmentFormChange={org.setDepartmentForm}
      onGovernanceTabChange={org.setGovernanceTab}
      onPrimaryDepartmentAction={org.handlePrimaryDepartmentAction}
      onPrimaryUserAction={org.handlePrimaryUserAction}
      onRefetchDepartments={org.refetchDepartments}
      onRefreshOrg={org.refreshOrg}
      onResetUserPassword={org.handleResetUserPassword}
      onRoleFormChange={org.setRoleForm}
      onSelectDepartment={org.setSelectedDepartmentId}
      onSetupTabChange={org.setSetupTab}
      onTabChange={org.setActiveTab}
      onToggleUserStatus={org.handleToggleUserStatus}
      onUpdateCostCenter={org.handleUpdateCostCenter}
      onUpdateDepartment={org.handleUpdateDepartment}
      onUpdateRole={org.handleUpdateRole}
      onUpdateUser={org.handleUpdateUser}
      onUserFormChange={org.setUserForm}
      passwordResettingUserId={org.passwordResettingUserId}
      roleDeletingId={org.roleDeletingId}
      roleForm={org.roleForm}
      roleList={org.roleList}
      rolePermissions={org.rolePermissions ?? []}
      rolePermissionsError={org.rolePermissionsError}
      rolePermissionsLoading={org.rolePermissionsLoading}
      rolePresets={org.rolePresets ?? []}
      rolePresetsError={org.rolePresetsError}
      rolePresetsLoading={org.rolePresetsLoading}
      roleUpdatingId={org.roleUpdatingId}
      rolesError={org.rolesError}
      rolesLoading={org.rolesLoading}
      saving={org.saving}
      selectableCostCenters={org.selectableCostCenters}
      selectedDepartment={org.selectedDepartment}
      setupTab={org.setupTab}
      statusUpdatingUserId={org.statusUpdatingUserId}
      tree={org.departmentsData?.tree ?? []}
      userForm={org.userForm}
      userList={org.usersList}
      userUpdatingId={org.userUpdatingId}
      usersError={org.usersError}
      usersLoading={org.usersLoading}
      visibleUsers={org.visibleUsers}
    />
  );
}
