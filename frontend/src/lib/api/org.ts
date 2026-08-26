import { apiDelete, apiGet, apiPatch, apiPost } from "./core";

export interface DepartmentCreateRequest {
  parent_id?: string | null;
  name: string;
  description?: string | null;
  sort_order: number;
}

export interface DepartmentUpdateRequest {
  parent_id?: string | null;
  name?: string | null;
  description?: string | null;
  sort_order?: number | null;
}

export interface DepartmentResponse {
  id: string;
  tenant_id: string;
  parent_id: string | null;
  name: string;
  description: string | null;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface DepartmentTreeNode extends DepartmentResponse {
  children: DepartmentTreeNode[];
}

export interface DepartmentListResponse {
  departments: DepartmentResponse[];
  tree: DepartmentTreeNode[];
  total: number;
}

export interface CostCenterCreateRequest {
  department_id?: string | null;
  code: string;
  name: string;
  description?: string | null;
  monthly_budget_usd?: string | number | null;
  is_active: boolean;
}

export interface CostCenterUpdateRequest {
  department_id?: string | null;
  code?: string | null;
  name?: string | null;
  description?: string | null;
  monthly_budget_usd?: string | number | null;
  is_active?: boolean | null;
}

export interface CostCenterResponse {
  id: string;
  tenant_id: string;
  department_id: string | null;
  code: string;
  name: string;
  description: string | null;
  monthly_budget_usd: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CostCenterListResponse {
  cost_centers: CostCenterResponse[];
  total: number;
}

export interface UserDepartmentBindingRequest {
  department_id: string;
  is_leader: boolean;
  is_primary: boolean;
  position_title?: string | null;
  cost_center_id?: string | null;
}

export interface UserDepartmentBindingResponse extends UserDepartmentBindingRequest {
  department_name: string | null;
  cost_center_code: string | null;
  cost_center_name: string | null;
}

export interface UserCreateRequest {
  email: string;
  password: string;
  username?: string | null;
  full_name?: string | null;
  avatar_url?: string | null;
  phone?: string | null;
  is_tenant_admin: boolean;
  is_active: boolean;
  department_bindings: UserDepartmentBindingRequest[];
  role_ids: string[];
}

export interface UserUpdateRequest {
  email?: string | null;
  username?: string | null;
  full_name?: string | null;
  avatar_url?: string | null;
  phone?: string | null;
  is_tenant_admin?: boolean | null;
  department_bindings?: UserDepartmentBindingRequest[] | null;
  role_ids?: string[] | null;
}

export interface UserStatusUpdateRequest {
  is_active: boolean;
}

export interface UserPasswordResetRequest {
  new_password: string;
}

export interface UserRoleResponse {
  id: string;
  name: string;
  description: string | null;
  permissions: string[];
  is_system: boolean;
}

export interface UserResponse {
  id: string;
  tenant_id: string;
  email: string;
  username: string | null;
  full_name: string | null;
  avatar_url: string | null;
  phone: string | null;
  is_super_admin: boolean;
  is_tenant_admin: boolean;
  is_active: boolean;
  last_login_at: string | null;
  departments: UserDepartmentBindingResponse[];
  roles: UserRoleResponse[];
  permissions: string[];
  created_at: string;
  updated_at: string;
}

export interface UserListResponse {
  users: UserResponse[];
  total: number;
}

export interface RoleCreateRequest {
  name: string;
  description?: string | null;
  permissions: string[];
  is_system: boolean;
}

export interface RoleUpdateRequest {
  name?: string | null;
  description?: string | null;
  permissions?: string[] | null;
}

export interface RoleResponse {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  permissions: string[];
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

export interface RoleListResponse {
  roles: RoleResponse[];
  total: number;
}

export interface RoleDeleteResponse {
  id: string;
  deleted: boolean;
}

export interface DeleteResponse {
  id: string;
  deleted: boolean;
}

export interface PermissionCatalogItem {
  value: string;
  category: string;
  label: string;
}

export interface PermissionCatalogResponse {
  permissions: PermissionCatalogItem[];
  total: number;
}

export interface RolePresetItem {
  key: string;
  name: string;
  description: string;
  permissions: string[];
  scope: string;
  category: string;
}

export interface RolePresetResponse {
  presets: RolePresetItem[];
  total: number;
}

export const orgApi = {
  getDepartments: () => apiGet<DepartmentListResponse>("/api/v1/orgs/departments"),
  createDepartment: (payload: DepartmentCreateRequest) =>
    apiPost<DepartmentResponse, DepartmentCreateRequest>("/api/v1/orgs/departments", payload),
  updateDepartment: (departmentId: string, payload: DepartmentUpdateRequest) =>
    apiPatch<DepartmentResponse, DepartmentUpdateRequest>(`/api/v1/orgs/departments/${departmentId}`, payload),
  deleteDepartment: (departmentId: string) => apiDelete<DeleteResponse>(`/api/v1/orgs/departments/${departmentId}`),
  getCostCenters: () => apiGet<CostCenterListResponse>("/api/v1/orgs/cost-centers"),
  createCostCenter: (payload: CostCenterCreateRequest) =>
    apiPost<CostCenterResponse, CostCenterCreateRequest>("/api/v1/orgs/cost-centers", payload),
  updateCostCenter: (costCenterId: string, payload: CostCenterUpdateRequest) =>
    apiPatch<CostCenterResponse, CostCenterUpdateRequest>(`/api/v1/orgs/cost-centers/${costCenterId}`, payload),
  deleteCostCenter: (costCenterId: string) => apiDelete<DeleteResponse>(`/api/v1/orgs/cost-centers/${costCenterId}`),
  getUsers: () => apiGet<UserListResponse>("/api/v1/users"),
  createUser: (payload: UserCreateRequest) => apiPost<UserResponse, UserCreateRequest>("/api/v1/users", payload),
  updateUser: (userId: string, payload: UserUpdateRequest) =>
    apiPatch<UserResponse, UserUpdateRequest>(`/api/v1/users/${userId}`, payload),
  updateUserStatus: (userId: string, payload: UserStatusUpdateRequest) =>
    apiPatch<UserResponse, UserStatusUpdateRequest>(`/api/v1/users/${userId}/status`, payload),
  resetUserPassword: (userId: string, payload: UserPasswordResetRequest) =>
    apiPatch<UserResponse, UserPasswordResetRequest>(`/api/v1/users/${userId}/password`, payload),
  getRoles: () => apiGet<RoleListResponse>("/api/v1/roles"),
  getRolePermissions: () => apiGet<PermissionCatalogResponse>("/api/v1/roles/permissions"),
  getRolePresets: () => apiGet<RolePresetResponse>("/api/v1/roles/presets"),
  createRole: (payload: RoleCreateRequest) => apiPost<RoleResponse, RoleCreateRequest>("/api/v1/roles", payload),
  updateRole: (roleId: string, payload: RoleUpdateRequest) =>
    apiPatch<RoleResponse, RoleUpdateRequest>(`/api/v1/roles/${roleId}`, payload),
  deleteRole: (roleId: string) => apiDelete<RoleDeleteResponse>(`/api/v1/roles/${roleId}`),
};
