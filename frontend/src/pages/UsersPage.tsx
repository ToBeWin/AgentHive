import { Plus, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { ApiNotice, Button, cx, LoadingState, PageHeader } from "../components/app-ui";
import { useCostCenters, useDepartments, useOrgAdminActions, useRoles, useUsers } from "../hooks/useAdminData";
import { useLocale } from "../i18n-context";
import { getStoredAuthUser, type UserUpdateRequest } from "../lib/api";
import { canAccess } from "../lib/permissions";
import type { UserFormState } from "./departments/departmentUtils";
import { UserQuickCreatePanel } from "./departments/UserQuickCreatePanel";
import { UsersTable } from "./departments/UsersTable";

const EMPTY_USER_FORM: UserFormState = {
  costCenterId: "",
  email: "",
  fullName: "",
  password: "",
  roleId: "",
};

type StatusFilter = "" | "active" | "inactive";

export function UsersPage({ isPrototype = false }: { isPrototype?: boolean }) {
  const { t } = useLocale();
  const canWriteUsers = isPrototype || canAccess(getStoredAuthUser(), ["users:write"]);
  const [search, setSearch] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("");
  const [showCreate, setShowCreate] = useState(false);
  const [userForm, setUserForm] = useState<UserFormState>(EMPTY_USER_FORM);

  const users = useUsers({ fallbackOnError: isPrototype });
  const departments = useDepartments({ fallbackOnError: isPrototype });
  const costCenters = useCostCenters({ fallbackOnError: isPrototype });
  const roles = useRoles({ fallbackOnError: isPrototype });

  const actionLabels = useMemo(
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
      userCreated: t("usersCreated"),
      userUpdated: t("departmentsUserUpdated"),
      userPasswordReset: t("departmentsUserPasswordReset"),
      userStatusUpdated: t("departmentsUserStatusUpdated"),
    }),
    [t],
  );
  const actions = useOrgAdminActions(actionLabels);

  const departmentList = departments.data?.departments ?? [];
  const costCenterList = costCenters.data ?? [];
  const roleList = roles.data ?? [];
  const allUsers = users.data ?? [];

  const filteredUsers = useMemo(() => {
    const query = search.trim().toLowerCase();
    return allUsers.filter((user) => {
      if (query) {
        const haystack = `${user.email} ${user.full_name ?? ""} ${user.username ?? ""}`.toLowerCase();
        if (!haystack.includes(query)) {
          return false;
        }
      }
      if (departmentFilter && !user.departments.some((binding) => binding.department_id === departmentFilter)) {
        return false;
      }
      if (statusFilter === "active" && !user.is_active) {
        return false;
      }
      if (statusFilter === "inactive" && user.is_active) {
        return false;
      }
      return true;
    });
  }, [allUsers, departmentFilter, search, statusFilter]);

  const selectableCostCenters = useMemo(
    () => costCenterList.filter((costCenter) => !costCenter.department_id),
    [costCenterList],
  );

  const refreshUsers = async () => {
    await users.refetch();
  };

  const handleCreateUser = async () => {
    if (!canWriteUsers) {
      return;
    }
    const created = await actions.createUser({
      department_bindings: [],
      email: userForm.email.trim(),
      full_name: userForm.fullName.trim(),
      is_active: true,
      is_tenant_admin: false,
      password: userForm.password,
      role_ids: userForm.roleId ? [userForm.roleId] : [],
      username: null,
    });
    if (created) {
      setUserForm(EMPTY_USER_FORM);
      setShowCreate(false);
      await refreshUsers();
    }
  };

  const handleUpdateUser = async (userId: string, payload: UserUpdateRequest) => {
    if (!canWriteUsers) {
      return false;
    }
    const updated = await actions.updateUser(userId, payload);
    if (updated) {
      await refreshUsers();
      return true;
    }
    return false;
  };

  const handleToggleUserStatus = async (userId: string, isActive: boolean) => {
    if (!canWriteUsers) {
      return;
    }
    const updated = await actions.updateUserStatus(userId, isActive);
    if (updated) {
      await refreshUsers();
    }
  };

  const handleResetUserPassword = async (userId: string, password: string) => {
    if (!canWriteUsers) {
      return false;
    }
    const updated = await actions.resetUserPassword(userId, password);
    if (updated) {
      await refreshUsers();
      return true;
    }
    return false;
  };

  const loadError = users.error ?? departments.error ?? costCenters.error ?? roles.error ?? null;

  return (
    <section className="page users-page">
      <PageHeader
        title={t("usersPageTitle")}
        subtitle={t("usersPageSubtitle")}
        actions={
          canWriteUsers ? (
            <Button variant="primary" onClick={() => setShowCreate(true)}>
              <Plus size={16} /> {t("usersCreate")}
            </Button>
          ) : undefined
        }
      />
      {loadError && (
        <ApiNotice
          title={t("departmentsOrgApiNotice")}
          message={loadError}
          action={<Button onClick={users.refetch}>{t("commonRetry")}</Button>}
        />
      )}
      {(actions.error || actions.message) && (
        <div className={cx("form-message", actions.error ? "error" : false)}>{actions.error ?? actions.message}</div>
      )}
      <div className="users-filters">
        <div className="agent-knowledge-search users-search">
          <Search size={15} />
          <input
            placeholder={t("usersSearchPlaceholder")}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          {search && (
            <button
              type="button"
              className="filter-clear-button"
              aria-label={t("commonClose")}
              onClick={() => setSearch("")}
            >
              <X size={14} />
            </button>
          )}
        </div>
        <select
          value={departmentFilter}
          onChange={(event) => setDepartmentFilter(event.target.value)}
          title={t("usersFilterAllDepartments")}
        >
          <option value="">{t("usersFilterAllDepartments")}</option>
          {departmentList.map((department) => (
            <option key={department.id} value={department.id}>
              {department.name}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
          title={t("usersFilterAllStatuses")}
        >
          <option value="">{t("usersFilterAllStatuses")}</option>
          <option value="active">{t("usersFilterStatusActive")}</option>
          <option value="inactive">{t("usersFilterStatusInactive")}</option>
        </select>
        {(departmentFilter || statusFilter) && (
          <button
            type="button"
            className="filter-reset-button"
            onClick={() => {
              setDepartmentFilter("");
              setStatusFilter("");
            }}
          >
            <X size={14} /> {t("usersFilterReset")}
          </button>
        )}
      </div>
      {users.loading && !allUsers.length && <LoadingState message={t("departmentsLoadingUsers")} lines={3} />}
      {users.loading && !!allUsers.length && (
        <div className="refresh-indicator" role="status" aria-live="polite">
          <span className="refresh-spinner" aria-hidden="true" />
          {t("commonRefreshing")}
        </div>
      )}
      <UsersTable
        canWriteUsers={canWriteUsers}
        costCenters={costCenterList}
        departments={departmentList}
        loading={users.loading && !allUsers.length}
        onResetUserPassword={handleResetUserPassword}
        onToggleUserStatus={handleToggleUserStatus}
        onUpdateUser={handleUpdateUser}
        passwordResettingUserId={actions.passwordResettingUserId}
        roles={roleList}
        selectedDepartment={null}
        showCostCenter={false}
        statusUpdatingUserId={actions.statusUpdatingUserId}
        updatingUserId={actions.userUpdatingId}
        users={filteredUsers}
      />
      {canWriteUsers && showCreate && (
        <UserCreateDrawer
          onClose={() => setShowCreate(false)}
          onCreateUser={handleCreateUser}
          onUserFormChange={setUserForm}
          roles={roleList}
          saving={actions.saving}
          selectableCostCenters={selectableCostCenters}
          userForm={userForm}
        />
      )}
    </section>
  );
}

interface UserCreateDrawerProps {
  onClose: () => void;
  onCreateUser: () => void;
  onUserFormChange: (form: UserFormState) => void;
  roles: ReturnType<typeof useRoles>["data"];
  saving: boolean;
  selectableCostCenters: ReturnType<typeof useCostCenters>["data"];
  userForm: UserFormState;
}

function UserCreateDrawer({
  onClose,
  onCreateUser,
  onUserFormChange,
  roles,
  saving,
  selectableCostCenters,
  userForm,
}: UserCreateDrawerProps) {
  const { t } = useLocale();
  return (
    <>
      <button type="button" aria-label={t("commonClose")} className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer user-create-drawer" role="dialog" aria-modal="true" aria-label={t("usersCreateTitle")}>
        <header>
          <div>
            <h2>{t("usersCreateTitle")}</h2>
            <p>{t("departmentsUserAccessNote")}</p>
          </div>
          <Button variant="ghost" onClick={onClose}>
            <X size={16} /> {t("commonClose")}
          </Button>
        </header>
        <div className="drawer-content">
          <UserQuickCreatePanel
            onCreateUser={onCreateUser}
            onUserFormChange={onUserFormChange}
            roles={roles ?? []}
            saving={saving}
            selectableCostCenters={selectableCostCenters ?? []}
            userForm={userForm}
          />
        </div>
      </aside>
    </>
  );
}
