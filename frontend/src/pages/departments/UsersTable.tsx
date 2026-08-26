import { Users } from "lucide-react";
import { Fragment, useState } from "react";
import { Button, ConfirmDialog, EmptyState, StatusBadge } from "../../components/app-ui";
import { SortableTh, type SortDirection, sortItems } from "../../components/SortableTh";
import { DEFAULT_PAGE_SIZE, paginate, TablePagination } from "../../components/TablePagination";
import { useLocale } from "../../i18n-context";
import {
  type CostCenterResponse,
  type DepartmentResponse,
  getStoredAuthUser,
  type RoleResponse,
  type UserResponse,
  type UserUpdateRequest,
} from "../../lib/api";
import { canAccess } from "../../lib/permissions";
import { getStoredPrototypeMode } from "../../lib/runtimeMode";
import { formatDate, formatUserStatus, getUserStatusLabelKey, initials, userDisplayName } from "./departmentUtils";
import { UserEditRow } from "./UserEditRow";
import { UserPasswordResetRow } from "./UserPasswordResetRow";

export function UsersTable({
  canWriteUsers = getStoredPrototypeMode() || canAccess(getStoredAuthUser(), ["users:write"]),
  costCenters,
  departments,
  loading,
  onResetUserPassword,
  onToggleUserStatus,
  onUpdateUser,
  passwordResettingUserId,
  roles,
  selectedDepartment,
  showCostCenter = true,
  statusUpdatingUserId,
  updatingUserId,
  users,
}: {
  canWriteUsers?: boolean;
  costCenters: CostCenterResponse[];
  departments: DepartmentResponse[];
  loading: boolean;
  onResetUserPassword: (userId: string, password: string) => Promise<boolean>;
  onToggleUserStatus: (userId: string, isActive: boolean) => void;
  onUpdateUser: (userId: string, payload: UserUpdateRequest) => Promise<boolean>;
  passwordResettingUserId: string | null;
  roles: RoleResponse[];
  selectedDepartment: DepartmentResponse | null;
  showCostCenter?: boolean;
  statusUpdatingUserId: string | null;
  updatingUserId: string | null;
  users: UserResponse[];
}) {
  const { locale, t } = useLocale();
  const [editingUserId, setEditingUserId] = useState<string | null>(null);
  const [resettingUserId, setResettingUserId] = useState<string | null>(null);
  const [pendingDeactivateUser, setPendingDeactivateUser] = useState<UserResponse | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>(null);
  const [lastUserCount, setLastUserCount] = useState(users.length);
  if (users.length !== lastUserCount) {
    setLastUserCount(users.length);
    setPage(1);
  }

  const handleSort = (key: string, direction: SortDirection) => {
    setSortKey(key);
    setSortDirection(direction);
    setPage(1);
  };

  const sortedUsers =
    sortKey && sortDirection
      ? sortItems(users, sortKey, sortDirection, (item, key) => {
          switch (key) {
            case "full_name":
              return item.full_name || item.username || item.email || "";
            case "email":
              return item.email || "";
            case "created_at":
              return new Date(item.created_at || 0);
            case "last_login_at":
              return item.last_login_at ? new Date(item.last_login_at) : new Date(0);
            default:
              return "";
          }
        })
      : users;

  const totalPages = Math.max(1, Math.ceil(sortedUsers.length / pageSize));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const pagedUsers = paginate(sortedUsers, { page: safePage, pageSize });

  const handleToggleStatus = (user: UserResponse) => {
    if (!canWriteUsers) {
      return;
    }
    if (user.is_active) {
      setPendingDeactivateUser(user);
      return;
    }
    onToggleUserStatus(user.id, !user.is_active);
  };

  const confirmDeactivateUser = () => {
    if (!canWriteUsers) {
      setPendingDeactivateUser(null);
      return;
    }
    const target = pendingDeactivateUser;
    setPendingDeactivateUser(null);
    if (target) {
      onToggleUserStatus(target.id, false);
    }
  };

  const colSpan = (showCostCenter ? 6 : 5) + (canWriteUsers ? 1 : 0);

  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <SortableTh
              label={t("departmentsUser")}
              sortKey="full_name"
              currentSortKey={sortKey ?? undefined}
              currentDirection={sortDirection ?? undefined}
              onSort={handleSort}
            />
            <th>{t("departmentsRoleColumn")}</th>
            <th>{t("departmentsDepartmentColumn")}</th>
            {showCostCenter && <th>{t("departmentsCostCenterColumn")}</th>}
            <SortableTh
              label={t("departmentsLastLogin")}
              sortKey="last_login_at"
              currentSortKey={sortKey ?? undefined}
              currentDirection={sortDirection ?? undefined}
              onSort={handleSort}
            />
            <th>{t("departmentsStatus")}</th>
            {canWriteUsers && <th>{t("departmentsActions")}</th>}
          </tr>
        </thead>
        <tbody>
          {loading && (
            <tr>
              <td colSpan={colSpan}>{t("departmentsLoadingUsers")}</td>
            </tr>
          )}
          {!loading && !users.length && (
            <tr>
              <td colSpan={colSpan} className="table-empty-cell">
                <EmptyState icon={<Users />} title={t("departmentsNoUsers")} />
              </td>
            </tr>
          )}
          {pagedUsers.map((user) => {
            const displayName = userDisplayName(user);
            const primaryDepartment =
              user.departments.find((department) => department.is_primary) ?? user.departments[0];
            const primaryRole = user.roles[0];
            const status = formatUserStatus(user);
            const isEditing = canWriteUsers && editingUserId === user.id;
            const isResetting = canWriteUsers && resettingUserId === user.id;
            return (
              <Fragment key={user.id}>
                <tr>
                  <td>
                    <span className="avatar small">{initials(displayName) || "U"}</span>
                    <div>
                      <strong>{displayName}</strong>
                      <span className="row-subtitle">{user.email}</span>
                    </div>
                  </td>
                  <td>
                    {primaryRole?.name ??
                      (user.is_tenant_admin ? t("departmentsTenantAdmin") : t("departmentsUnassigned"))}
                  </td>
                  <td>
                    {primaryDepartment?.department_name ?? selectedDepartment?.name ?? t("departmentsUnassigned")}
                  </td>
                  {showCostCenter && (
                    <td>
                      <code>
                        {primaryDepartment?.cost_center_code ?? costCenters[0]?.code ?? t("departmentsNotApplicable")}
                      </code>
                    </td>
                  )}
                  <td>{formatDate(user.last_login_at, locale, t("departmentsNotSet"))}</td>
                  <td>
                    <StatusBadge label={t(getUserStatusLabelKey(status))} status={status} />
                  </td>
                  {canWriteUsers && (
                    <td>
                      <div className="table-action-row">
                        <Button
                          onClick={() => {
                            setResettingUserId(null);
                            setEditingUserId(isEditing ? null : user.id);
                          }}
                        >
                          {isEditing ? t("departmentsCloseUserEdit") : t("departmentsEditUser")}
                        </Button>
                        <Button onClick={() => handleToggleStatus(user)} disabled={statusUpdatingUserId === user.id}>
                          {statusUpdatingUserId === user.id
                            ? t("departmentsUpdatingUser")
                            : user.is_active
                              ? t("departmentsDeactivateUser")
                              : t("departmentsActivateUser")}
                        </Button>
                        <Button
                          onClick={() => {
                            setEditingUserId(null);
                            setResettingUserId(isResetting ? null : user.id);
                          }}
                          disabled={passwordResettingUserId === user.id}
                        >
                          {passwordResettingUserId === user.id
                            ? t("departmentsResettingPassword")
                            : isResetting
                              ? t("departmentsCloseUserEdit")
                              : t("departmentsResetPassword")}
                        </Button>
                      </div>
                    </td>
                  )}
                </tr>
                {isEditing && (
                  <tr>
                    <td className="user-edit-cell" colSpan={colSpan}>
                      <UserEditRow
                        costCenters={costCenters}
                        departments={departments}
                        onCancel={() => setEditingUserId(null)}
                        onSave={onUpdateUser}
                        roles={roles}
                        saving={updatingUserId === user.id}
                        user={user}
                      />
                    </td>
                  </tr>
                )}
                {isResetting && (
                  <tr>
                    <td className="user-edit-cell" colSpan={colSpan}>
                      <UserPasswordResetRow
                        onCancel={() => setResettingUserId(null)}
                        onSave={onResetUserPassword}
                        saving={passwordResettingUserId === user.id}
                        user={user}
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
      <TablePagination
        total={users.length}
        page={safePage}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
        }}
      />
      <ConfirmDialog
        open={canWriteUsers && Boolean(pendingDeactivateUser)}
        title={t("departmentsDeactivateUser")}
        message={
          pendingDeactivateUser
            ? t("departmentsDeactivateUserConfirm").replace("{{email}}", pendingDeactivateUser.email)
            : ""
        }
        confirmLabel={t("departmentsDeactivateUser")}
        cancelLabel={t("commonClose")}
        variant="danger"
        onConfirm={confirmDeactivateUser}
        onCancel={() => setPendingDeactivateUser(null)}
      />
    </div>
  );
}
