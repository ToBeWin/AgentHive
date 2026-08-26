import type {
  CostCenterResponse,
  DepartmentResponse,
  RoleResponse,
  UserResponse,
  UserUpdateRequest,
} from "../../lib/api";
import { UsersTable } from "./UsersTable";

interface DepartmentsPeopleWorkspaceProps {
  costCenters: CostCenterResponse[];
  departments: DepartmentResponse[];
  loading: boolean;
  onResetUserPassword: (userId: string, password: string) => Promise<boolean>;
  onToggleUserStatus: (userId: string, isActive: boolean) => void;
  onUpdateUser: (userId: string, payload: UserUpdateRequest) => Promise<boolean>;
  passwordResettingUserId: string | null;
  roles: RoleResponse[];
  selectedDepartment: DepartmentResponse | null;
  statusUpdatingUserId: string | null;
  updatingUserId: string | null;
  users: UserResponse[];
}

export function DepartmentsPeopleWorkspace({
  costCenters,
  departments,
  loading,
  onResetUserPassword,
  onToggleUserStatus,
  onUpdateUser,
  passwordResettingUserId,
  roles,
  selectedDepartment,
  statusUpdatingUserId,
  updatingUserId,
  users,
}: DepartmentsPeopleWorkspaceProps) {
  return (
    <UsersTable
      costCenters={costCenters}
      departments={departments}
      loading={loading}
      onResetUserPassword={onResetUserPassword}
      onToggleUserStatus={onToggleUserStatus}
      onUpdateUser={onUpdateUser}
      passwordResettingUserId={passwordResettingUserId}
      roles={roles}
      selectedDepartment={selectedDepartment}
      statusUpdatingUserId={statusUpdatingUserId}
      updatingUserId={updatingUserId}
      users={users}
    />
  );
}
