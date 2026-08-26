import { useEffect, useMemo, useState } from "react";
import {
  useCostCenters,
  useDepartments,
  useOrgAdminActions,
  useRolePermissions,
  useRolePresets,
  useRoles,
  useUsers,
} from "../../hooks/useAdminData";
import { useLocale } from "../../i18n-context";
import type { CostCenterUpdateRequest, DepartmentUpdateRequest, UserUpdateRequest } from "../../lib/api";
import type { DepartmentsGovernanceTab, DepartmentsPageTab } from "./DepartmentsWorkspace";
import type { CostCenterFormState, DepartmentFormState, RoleFormState, UserFormState } from "./departmentUtils";
import { parsePermissionInput, preferredCostCenterForDepartment } from "./departmentUtils";
import type { OrgSetupTab } from "./OrgQuickActionsPanel";
import { roleEditFormToPayload } from "./RoleManagementPanel";

export function useDepartmentsPageController({ isPrototype = false }: { isPrototype?: boolean }) {
  const { t } = useLocale();
  const [activeTab, setActiveTab] = useState<DepartmentsPageTab>("people");
  const [setupTab, setSetupTab] = useState<OrgSetupTab>("user");
  const [governanceTab, setGovernanceTab] = useState<DepartmentsGovernanceTab>("department");
  const {
    data: departmentsData,
    error: departmentsError,
    loading: departmentsLoading,
    refetch: refetchDepartments,
  } = useDepartments({ fallbackOnError: isPrototype });
  const {
    data: costCenters,
    error: costCentersError,
    loading: costCentersLoading,
    refetch: refetchCostCenters,
  } = useCostCenters({ fallbackOnError: isPrototype });
  const {
    data: apiUsers,
    error: usersError,
    loading: usersLoading,
    refetch: refetchUsers,
  } = useUsers({ fallbackOnError: isPrototype });
  const {
    data: roles,
    error: rolesError,
    loading: rolesLoading,
    refetch: refetchRoles,
  } = useRoles({ fallbackOnError: isPrototype });
  const {
    data: rolePermissions,
    error: rolePermissionsError,
    loading: rolePermissionsLoading,
    refetch: refetchRolePermissions,
  } = useRolePermissions({ fallbackOnError: isPrototype });
  const {
    data: rolePresets,
    error: rolePresetsError,
    loading: rolePresetsLoading,
    refetch: refetchRolePresets,
  } = useRolePresets({ fallbackOnError: isPrototype });
  const orgActionLabels = useMemo(
    () => ({
      costCenterCreated: t("departmentsCostCenterCreated"),
      costCenterDeleted: t("departmentsCostCenterDeleted"),
      costCenterUpdated: t("departmentsCostCenterUpdated"),
      departmentCreated: t("departmentsDepartmentCreated"),
      departmentDeleted: t("departmentsDepartmentDeleted"),
      departmentUpdated: t("departmentsDepartmentUpdated"),
      roleCreated: t("departmentsRoleCreated"),
      roleDeleted: t("departmentsRoleDeleted"),
      roleUpdated: t("departmentsRoleUpdated"),
      userCreated: t("departmentsUserCreated"),
      userPasswordReset: t("departmentsUserPasswordReset"),
      userStatusUpdated: t("departmentsUserStatusUpdated"),
      userUpdated: t("departmentsUserUpdated"),
    }),
    [t],
  );
  const {
    createCostCenter,
    createDepartment,
    createRole,
    createUser,
    deleteCostCenter,
    deleteDepartment,
    deleteRole,
    error: actionError,
    message: actionMessage,
    passwordResettingUserId,
    resetUserPassword,
    roleDeletingId,
    roleUpdatingId,
    saving,
    statusUpdatingUserId,
    updateCostCenter,
    updateDepartment,
    updateRole,
    updateUser,
    updateUserStatus,
    userUpdatingId,
  } = useOrgAdminActions(orgActionLabels);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState<string | null>(null);
  const [departmentForm, setDepartmentForm] = useState<DepartmentFormState>({
    description: "",
    name: "Customer Success",
  });
  const [costCenterForm, setCostCenterForm] = useState<CostCenterFormState>({
    code: "CS",
    monthlyBudget: "1000",
    name: "Customer Success",
  });
  const [roleForm, setRoleForm] = useState<RoleFormState>({
    description: "Can manage approved Agent operations.",
    name: "Agent Manager",
    permissions: "agents:read,chat:read,chat:write",
    templateKey: "",
  });
  const [userForm, setUserForm] = useState<UserFormState>({
    costCenterId: "",
    email: "new.user@example.com",
    fullName: "New User",
    password: "",
    roleId: "",
  });

  const departments = departmentsData?.departments ?? [];
  const selectedDepartment =
    departments.find((department) => department.id === selectedDepartmentId) ?? departments[0] ?? null;
  const usersList = apiUsers ?? [];
  const filteredUsers = selectedDepartment
    ? usersList.filter((user) => user.departments.some((binding) => binding.department_id === selectedDepartment.id))
    : usersList;
  const visibleUsers = selectedDepartment && filteredUsers.length ? filteredUsers : usersList;
  const roleList = roles ?? [];
  const costCenterList = costCenters ?? [];
  const preferredCostCenter = preferredCostCenterForDepartment(costCenterList, selectedDepartment);
  const selectableCostCenters = useMemo(
    () =>
      costCenterList.filter(
        (costCenter) =>
          !costCenter.department_id || !selectedDepartment || costCenter.department_id === selectedDepartment.id,
      ),
    [costCenterList, selectedDepartment],
  );

  useEffect(() => {
    if (!selectedDepartmentId && departments.length) {
      setSelectedDepartmentId(departments[0].id);
    }
  }, [departments, selectedDepartmentId]);

  useEffect(() => {
    setUserForm((current) => {
      const roleId = roleList.some((role) => role.id === current.roleId) ? current.roleId : (roleList[0]?.id ?? "");
      const costCenterId = selectableCostCenters.some((costCenter) => costCenter.id === current.costCenterId)
        ? current.costCenterId
        : (preferredCostCenter?.id ?? "");
      if (roleId === current.roleId && costCenterId === current.costCenterId) {
        return current;
      }
      return { ...current, costCenterId, roleId };
    });
  }, [preferredCostCenter, roleList, selectableCostCenters]);

  const refreshOrg = async () => {
    await Promise.all([
      refetchDepartments(),
      refetchCostCenters(),
      refetchUsers(),
      refetchRoles(),
      refetchRolePermissions(),
      refetchRolePresets(),
    ]);
  };

  const handleCreateDepartment = async () => {
    const created = await createDepartment({
      description: departmentForm.description.trim() || null,
      name: departmentForm.name.trim(),
      parent_id: selectedDepartmentId,
      sort_order: departments.length + 1,
    });
    if (created) {
      setSelectedDepartmentId(created.id);
      await refreshOrg();
    }
  };

  const handlePrimaryDepartmentAction = () => {
    setSetupTab("department");
    if (activeTab !== "setup") {
      setActiveTab("setup");
      return;
    }
    if (setupTab === "department") {
      void handleCreateDepartment();
    }
  };

  const handleCreateCostCenter = async () => {
    const created = await createCostCenter({
      code: costCenterForm.code.trim(),
      department_id: selectedDepartmentId,
      description: null,
      is_active: true,
      monthly_budget_usd: costCenterForm.monthlyBudget.trim() || null,
      name: costCenterForm.name.trim(),
    });
    if (created) {
      await refreshOrg();
    }
  };

  const handleUpdateDepartment = async (departmentId: string, payload: DepartmentUpdateRequest) => {
    const updated = await updateDepartment(departmentId, payload);
    if (updated) {
      await refreshOrg();
      return true;
    }
    return false;
  };

  const handleDeleteDepartment = async (departmentId: string) => {
    const deleted = await deleteDepartment(departmentId);
    if (deleted) {
      if (selectedDepartmentId === departmentId) {
        setSelectedDepartmentId(null);
      }
      await refreshOrg();
      return true;
    }
    return false;
  };

  const handleUpdateCostCenter = async (costCenterId: string, payload: CostCenterUpdateRequest) => {
    const updated = await updateCostCenter(costCenterId, payload);
    if (updated) {
      await refreshOrg();
      return true;
    }
    return false;
  };

  const handleDeleteCostCenter = async (costCenterId: string) => {
    const deleted = await deleteCostCenter(costCenterId);
    if (deleted) {
      await refreshOrg();
      return true;
    }
    return false;
  };

  const handleCreateRole = async () => {
    const created = await createRole({
      description: roleForm.description.trim() || "Created from AgentHive admin console.",
      is_system: false,
      name: roleForm.name.trim(),
      permissions: parsePermissionInput(roleForm.permissions),
    });
    if (created) {
      await refreshOrg();
    }
  };

  const handleUpdateRole = async (
    roleId: string,
    form: {
      description: string;
      name: string;
      permissions: string;
    },
  ) => {
    const updated = await updateRole(roleId, roleEditFormToPayload(form));
    if (updated) {
      await refreshOrg();
      return true;
    }
    return false;
  };

  const handleDeleteRole = async (roleId: string) => {
    const deleted = await deleteRole(roleId);
    if (deleted) {
      await refreshOrg();
      return true;
    }
    return false;
  };

  const handleCreateUser = async () => {
    const created = await createUser({
      department_bindings: selectedDepartment
        ? [
            {
              cost_center_id: userForm.costCenterId || preferredCostCenter?.id || null,
              department_id: selectedDepartment.id,
              is_leader: false,
              is_primary: true,
              position_title: "Member",
            },
          ]
        : [],
      email: userForm.email.trim(),
      full_name: userForm.fullName.trim(),
      is_active: true,
      is_tenant_admin: false,
      password: userForm.password,
      role_ids: userForm.roleId ? [userForm.roleId] : [],
      username: null,
    });
    if (created) {
      await refreshOrg();
    }
  };

  const handlePrimaryUserAction = () => {
    setSetupTab("user");
    if (activeTab !== "setup") {
      setActiveTab("setup");
      return;
    }
    if (setupTab === "user") {
      void handleCreateUser();
    }
  };

  const handleUpdateUser = async (userId: string, payload: UserUpdateRequest) => {
    const updated = await updateUser(userId, payload);
    if (updated) {
      await refetchUsers();
      return true;
    }
    return false;
  };

  const handleToggleUserStatus = async (userId: string, isActive: boolean) => {
    const target = usersList.find((user) => user.id === userId);
    if (!target) {
      return;
    }
    const updated = await updateUserStatus(userId, isActive);
    if (updated) {
      await refetchUsers();
    }
  };

  const handleResetUserPassword = async (userId: string, password: string) => {
    const updated = await resetUserPassword(userId, password);
    if (updated) {
      await refetchUsers();
      return true;
    }
    return false;
  };

  return {
    actionError,
    actionMessage,
    activeTab,
    costCenterForm,
    costCenterList,
    costCentersError,
    costCentersLoading,
    departmentForm,
    departments,
    departmentsData,
    departmentsError,
    departmentsLoading,
    governanceTab,
    handleCreateCostCenter,
    handleCreateDepartment,
    handleCreateRole,
    handleCreateUser,
    handleDeleteCostCenter,
    handleDeleteDepartment,
    handleDeleteRole,
    handlePrimaryDepartmentAction,
    handlePrimaryUserAction,
    handleResetUserPassword,
    handleToggleUserStatus,
    handleUpdateCostCenter,
    handleUpdateDepartment,
    handleUpdateRole,
    handleUpdateUser,
    passwordResettingUserId,
    refetchDepartments,
    refreshOrg,
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
    setActiveTab,
    setCostCenterForm,
    setDepartmentForm,
    setGovernanceTab,
    setRoleForm,
    setSelectedDepartmentId,
    setSetupTab,
    setUserForm,
    setupTab,
    statusUpdatingUserId,
    userForm,
    usersList,
    userUpdatingId,
    usersError,
    usersLoading,
    visibleUsers,
  };
}
