import { useCallback, useEffect, useState } from "react";
import { useToast } from "../../components/app-ui";
import {
  adminApi,
  type CostCenterCreateRequest,
  type CostCenterResponse,
  type CostCenterUpdateRequest,
  type DepartmentCreateRequest,
  type DepartmentListResponse,
  type DepartmentResponse,
  type DepartmentUpdateRequest,
  type PermissionCatalogItem,
  type RoleCreateRequest,
  type RolePresetItem,
  type RoleResponse,
  type RoleUpdateRequest,
  type UserCreateRequest,
  type UserResponse,
  type UserUpdateRequest,
} from "../../lib/api";
import { type AsyncState, errorToMessage, withRetry } from "./shared";

export function useDepartments(options: { fallbackOnError?: boolean } = {}) {
  const [state, setState] = useState<AsyncState<DepartmentListResponse>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    try {
      const data = await withRetry(() => adminApi.getDepartments());
      if (options.fallbackOnError && !data.departments.length) {
        setState({ data: PROTOTYPE_DEPARTMENTS, error: null, loading: false });
        return;
      }
      setState({ data, error: null, loading: false });
    } catch (error) {
      if (options.fallbackOnError) {
        setState({ data: PROTOTYPE_DEPARTMENTS, error: null, loading: false });
        return;
      }
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [options.fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

export function useCostCenters(options: { fallbackOnError?: boolean } = {}) {
  const [state, setState] = useState<AsyncState<CostCenterResponse[]>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    try {
      const data = await adminApi.getCostCenters();
      if (options.fallbackOnError && !data.cost_centers.length) {
        setState({ data: PROTOTYPE_COST_CENTERS, error: null, loading: false });
        return;
      }
      setState({ data: data.cost_centers, error: null, loading: false });
    } catch (error) {
      if (options.fallbackOnError) {
        setState({ data: PROTOTYPE_COST_CENTERS, error: null, loading: false });
        return;
      }
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [options.fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

export function useUsers(options: { fallbackOnError?: boolean } = {}) {
  const [state, setState] = useState<AsyncState<UserResponse[]>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    try {
      const data = await withRetry(() => adminApi.getUsers());
      if (options.fallbackOnError && !data.users.length) {
        setState({ data: PROTOTYPE_USERS, error: null, loading: false });
        return;
      }
      setState({ data: data.users, error: null, loading: false });
    } catch (error) {
      if (options.fallbackOnError) {
        setState({ data: PROTOTYPE_USERS, error: null, loading: false });
        return;
      }
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [options.fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

const PROTOTYPE_NOW = "2026-01-01T00:00:00.000Z";
const PROTOTYPE_TENANT_ID = "00000000-0000-4000-8000-000000000001";
const PROTOTYPE_DEPARTMENT_ID = "00000000-0000-4000-8000-000000000301";
const PROTOTYPE_COST_CENTER_ID = "00000000-0000-4000-8000-000000000401";

const PROTOTYPE_DEPARTMENT: DepartmentResponse = {
  created_at: PROTOTYPE_NOW,
  description: "Owns customer-facing Agent workflows and knowledge quality.",
  id: PROTOTYPE_DEPARTMENT_ID,
  name: "Customer Success",
  parent_id: null,
  sort_order: 10,
  tenant_id: PROTOTYPE_TENANT_ID,
  updated_at: PROTOTYPE_NOW,
};

const PROTOTYPE_DEPARTMENTS: DepartmentListResponse = {
  departments: [PROTOTYPE_DEPARTMENT],
  total: 1,
  tree: [{ ...PROTOTYPE_DEPARTMENT, children: [] }],
};

const PROTOTYPE_COST_CENTERS: CostCenterResponse[] = [
  {
    code: "CS",
    created_at: PROTOTYPE_NOW,
    department_id: PROTOTYPE_DEPARTMENT_ID,
    description: "Monthly model spend for customer-facing Agent operations.",
    id: PROTOTYPE_COST_CENTER_ID,
    is_active: true,
    monthly_budget_usd: "2500.0000",
    name: "Customer Success",
    tenant_id: PROTOTYPE_TENANT_ID,
    updated_at: PROTOTYPE_NOW,
  },
];

const PROTOTYPE_ROLES: RoleResponse[] = [
  {
    created_at: PROTOTYPE_NOW,
    description: "Full tenant administration for the private AgentHive deployment.",
    id: "00000000-0000-4000-8000-000000000101",
    is_system: true,
    name: "Tenant Administrator",
    permissions: ["tenant.admin"],
    tenant_id: PROTOTYPE_TENANT_ID,
    updated_at: PROTOTYPE_NOW,
  },
  {
    created_at: PROTOTYPE_NOW,
    description: "Operate Agent instances, knowledge bases, and support workflows.",
    id: "00000000-0000-4000-8000-000000000102",
    is_system: false,
    name: "Agent Manager",
    permissions: ["agents:read", "agents:write", "chat:read", "chat:write", "knowledge:read", "knowledge:write"],
    tenant_id: PROTOTYPE_TENANT_ID,
    updated_at: PROTOTYPE_NOW,
  },
  {
    created_at: PROTOTYPE_NOW,
    description: "Export redacted diagnostics packages for private deployment support.",
    id: "00000000-0000-4000-8000-000000000103",
    is_system: false,
    name: "Implementation Operator",
    permissions: [
      "users:read",
      "departments:read",
      "agents:read",
      "chat:read",
      "channels:read",
      "channels:write",
      "license:read",
      "audit:read",
      "system:diagnostics",
    ],
    tenant_id: PROTOTYPE_TENANT_ID,
    updated_at: PROTOTYPE_NOW,
  },
];

const PROTOTYPE_ROLE_PRESETS: RolePresetItem[] = [
  {
    category: "administration",
    description: "Full tenant administration for users, departments, models, budgets, License, audit, and delivery.",
    key: "enterprise_admin",
    name: "Enterprise Admin",
    permissions: ["tenant.admin"],
    scope: "tenant",
  },
  {
    category: "operations",
    description: "Runs diagnostics, support bundles, upgrades, and private delivery troubleshooting.",
    key: "implementation_operator",
    name: "Ops / Implementation",
    permissions: [
      "users:read",
      "departments:read",
      "channels:read",
      "channels:write",
      "license:read",
      "audit:read",
      "system:diagnostics",
    ],
    scope: "tenant",
  },
  {
    category: "models",
    description: "Configures providers, Base URLs, API keys, model prices, routing policies, and budget guardrails.",
    key: "model_admin",
    name: "Model Admin",
    permissions: ["models:read", "models:write", "budgets:read", "audit:read"],
    scope: "tenant",
  },
  {
    category: "agents",
    description: "Installs Agent modules, manages Agent instances, and binds knowledge bases by department.",
    key: "agent_admin",
    name: "Agent Admin",
    permissions: [
      "agents:read",
      "agents:write",
      "chat:read",
      "chat:write",
      "knowledge:read",
      "knowledge:write",
      "channels:read",
    ],
    scope: "department",
  },
  {
    category: "governance",
    description: "Reviews department users, budget posture, Agent usage, and knowledge workflows.",
    key: "department_leader",
    name: "Department Leader",
    permissions: [
      "users:read",
      "departments:read",
      "agents:read",
      "chat:read",
      "knowledge:read",
      "budgets:read",
      "analytics:read",
    ],
    scope: "department",
  },
  {
    category: "employee",
    description: "Uses approved Agents and knowledge workflows with minimal configuration visibility.",
    key: "employee",
    name: "Employee",
    permissions: ["agents:read", "chat:read", "chat:write", "knowledge:read"],
    scope: "self",
  },
  {
    category: "audit",
    description: "Reviews audit records, budget ledgers, spend exports, and model cost evidence.",
    key: "audit_finance",
    name: "Audit / Finance",
    permissions: ["budgets:read", "budgets:export", "audit:read", "audit:export", "analytics:read"],
    scope: "tenant",
  },
];

const PROTOTYPE_USERS: UserResponse[] = [
  {
    avatar_url: null,
    created_at: PROTOTYPE_NOW,
    departments: [
      {
        cost_center_code: "CS",
        cost_center_id: PROTOTYPE_COST_CENTER_ID,
        cost_center_name: "Customer Success",
        department_id: PROTOTYPE_DEPARTMENT_ID,
        department_name: "Customer Success",
        is_leader: true,
        is_primary: true,
        position_title: "AI Program Owner",
      },
    ],
    email: "admin@agenthive.internal",
    full_name: "Deployment Admin",
    id: "00000000-0000-4000-8000-000000000201",
    is_active: true,
    is_super_admin: false,
    is_tenant_admin: true,
    last_login_at: PROTOTYPE_NOW,
    permissions: ["tenant.admin"],
    phone: null,
    roles: [
      {
        description: PROTOTYPE_ROLES[0].description,
        id: PROTOTYPE_ROLES[0].id,
        is_system: PROTOTYPE_ROLES[0].is_system,
        name: PROTOTYPE_ROLES[0].name,
        permissions: PROTOTYPE_ROLES[0].permissions,
      },
    ],
    tenant_id: PROTOTYPE_TENANT_ID,
    updated_at: PROTOTYPE_NOW,
    username: null,
  },
  {
    avatar_url: null,
    created_at: PROTOTYPE_NOW,
    departments: [
      {
        cost_center_code: "CS",
        cost_center_id: PROTOTYPE_COST_CENTER_ID,
        cost_center_name: "Customer Success",
        department_id: PROTOTYPE_DEPARTMENT_ID,
        department_name: "Customer Success",
        is_leader: false,
        is_primary: true,
        position_title: "Operations Lead",
      },
    ],
    email: "ops@example.com",
    full_name: "Operations Lead",
    id: "00000000-0000-4000-8000-000000000202",
    is_active: true,
    is_super_admin: false,
    is_tenant_admin: false,
    last_login_at: null,
    permissions: PROTOTYPE_ROLES[1].permissions,
    phone: "+1 555 0100",
    roles: [
      {
        description: PROTOTYPE_ROLES[1].description,
        id: PROTOTYPE_ROLES[1].id,
        is_system: PROTOTYPE_ROLES[1].is_system,
        name: PROTOTYPE_ROLES[1].name,
        permissions: PROTOTYPE_ROLES[1].permissions,
      },
    ],
    tenant_id: PROTOTYPE_TENANT_ID,
    updated_at: PROTOTYPE_NOW,
    username: null,
  },
];

export function useRoles(options: { fallbackOnError?: boolean } = {}) {
  const [state, setState] = useState<AsyncState<RoleResponse[]>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    try {
      const data = await withRetry(() => adminApi.getRoles());
      if (options.fallbackOnError && !data.roles.length) {
        setState({ data: PROTOTYPE_ROLES, error: null, loading: false });
        return;
      }
      setState({ data: data.roles, error: null, loading: false });
    } catch (error) {
      if (options.fallbackOnError) {
        setState({ data: PROTOTYPE_ROLES, error: null, loading: false });
        return;
      }
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [options.fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

const PROTOTYPE_ROLE_PERMISSIONS: PermissionCatalogItem[] = [
  { category: "admin", label: "Tenant administration", value: "tenant.admin" },
  { category: "organization", label: "Read users", value: "users:read" },
  { category: "organization", label: "Manage users", value: "users:write" },
  { category: "organization", label: "Read departments", value: "departments:read" },
  { category: "organization", label: "Manage departments", value: "departments:write" },
  { category: "agent", label: "Read agents", value: "agents:read" },
  { category: "agent", label: "Manage agents", value: "agents:write" },
  { category: "agent", label: "Read conversations", value: "chat:read" },
  { category: "agent", label: "Use Agents", value: "chat:write" },
  { category: "agent", label: "Read knowledge bases", value: "knowledge:read" },
  { category: "agent", label: "Manage knowledge bases", value: "knowledge:write" },
  { category: "channel", label: "Read channels", value: "channels:read" },
  { category: "channel", label: "Manage channels", value: "channels:write" },
  { category: "models", label: "Read model settings", value: "models:read" },
  { category: "models", label: "Manage model settings", value: "models:write" },
  { category: "budgets", label: "Read budgets", value: "budgets:read" },
  { category: "budgets", label: "Manage budgets", value: "budgets:write" },
  { category: "budgets", label: "Export budget ledgers", value: "budgets:export" },
  { category: "analytics", label: "Read analytics dashboards", value: "analytics:read" },
  { category: "audit", label: "Read audit logs", value: "audit:read" },
  { category: "audit", label: "Export audit logs", value: "audit:export" },
  { category: "license", label: "Read license", value: "license:read" },
  { category: "license", label: "Manage license", value: "license:write" },
  { category: "system", label: "Export system diagnostics", value: "system:diagnostics" },
];

export function useRolePermissions(options: { fallbackOnError?: boolean } = {}) {
  const [state, setState] = useState<AsyncState<PermissionCatalogItem[]>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    try {
      const data = await withRetry(() => adminApi.getRolePermissions());
      setState({ data: data.permissions, error: null, loading: false });
    } catch (error) {
      if (options.fallbackOnError) {
        setState({ data: PROTOTYPE_ROLE_PERMISSIONS, error: null, loading: false });
        return;
      }
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [options.fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

export function useRolePresets(options: { fallbackOnError?: boolean } = {}) {
  const [state, setState] = useState<AsyncState<RolePresetItem[]>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    try {
      const data = await withRetry(() => adminApi.getRolePresets());
      setState({ data: data.presets, error: null, loading: false });
    } catch (error) {
      if (options.fallbackOnError) {
        setState({ data: PROTOTYPE_ROLE_PRESETS, error: null, loading: false });
        return;
      }
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [options.fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

export function useOrgAdminActions(
  labels: {
    costCenterCreated: string;
    costCenterDeleted: string;
    costCenterUpdated: string;
    departmentCreated: string;
    departmentDeleted: string;
    departmentUpdated: string;
    roleCreated: string;
    roleDeleted: string;
    roleUpdated: string;
    userCreated: string;
    userUpdated: string;
    userPasswordReset: string;
    userStatusUpdated: string;
  } = {
    costCenterCreated: "Cost center created.",
    costCenterDeleted: "Cost center deleted.",
    costCenterUpdated: "Cost center updated.",
    departmentCreated: "Department created.",
    departmentDeleted: "Department deleted.",
    departmentUpdated: "Department updated.",
    roleCreated: "Role created.",
    roleDeleted: "Role deleted.",
    roleUpdated: "Role updated.",
    userCreated: "User created.",
    userUpdated: "User updated.",
    userPasswordReset: "User password reset.",
    userStatusUpdated: "User status updated.",
  },
) {
  const [saving, setSaving] = useState(false);
  const [passwordResettingUserId, setPasswordResettingUserId] = useState<string | null>(null);
  const [roleDeletingId, setRoleDeletingId] = useState<string | null>(null);
  const [roleUpdatingId, setRoleUpdatingId] = useState<string | null>(null);
  const [userUpdatingId, setUserUpdatingId] = useState<string | null>(null);
  const [statusUpdatingUserId, setStatusUpdatingUserId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { showToast } = useToast();

  const run = useCallback(
    async <T>(label: string, action: () => Promise<T>) => {
      setSaving(true);
      setMessage(null);
      setError(null);
      try {
        const response = await action();
        setMessage(label);
        showToast(label, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setSaving(false);
      }
    },
    [showToast],
  );

  const createDepartment = useCallback(
    (payload: DepartmentCreateRequest) => run(labels.departmentCreated, () => adminApi.createDepartment(payload)),
    [labels.departmentCreated, run],
  );
  const updateDepartment = useCallback(
    (departmentId: string, payload: DepartmentUpdateRequest) =>
      run(labels.departmentUpdated, () => adminApi.updateDepartment(departmentId, payload)),
    [labels.departmentUpdated, run],
  );
  const deleteDepartment = useCallback(
    (departmentId: string) => run(labels.departmentDeleted, () => adminApi.deleteDepartment(departmentId)),
    [labels.departmentDeleted, run],
  );
  const createCostCenter = useCallback(
    (payload: CostCenterCreateRequest) => run(labels.costCenterCreated, () => adminApi.createCostCenter(payload)),
    [labels.costCenterCreated, run],
  );
  const updateCostCenter = useCallback(
    (costCenterId: string, payload: CostCenterUpdateRequest) =>
      run(labels.costCenterUpdated, () => adminApi.updateCostCenter(costCenterId, payload)),
    [labels.costCenterUpdated, run],
  );
  const deleteCostCenter = useCallback(
    (costCenterId: string) => run(labels.costCenterDeleted, () => adminApi.deleteCostCenter(costCenterId)),
    [labels.costCenterDeleted, run],
  );
  const createUser = useCallback(
    (payload: UserCreateRequest) => run(labels.userCreated, () => adminApi.createUser(payload)),
    [labels.userCreated, run],
  );
  const updateUser = useCallback(
    async (userId: string, payload: UserUpdateRequest) => {
      setUserUpdatingId(userId);
      setMessage(null);
      setError(null);
      try {
        const response = await adminApi.updateUser(userId, payload);
        setMessage(labels.userUpdated);
        showToast(labels.userUpdated, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setUserUpdatingId(null);
      }
    },
    [labels.userUpdated, showToast],
  );
  const createRole = useCallback(
    (payload: RoleCreateRequest) => run(labels.roleCreated, () => adminApi.createRole(payload)),
    [labels.roleCreated, run],
  );
  const updateRole = useCallback(
    async (roleId: string, payload: RoleUpdateRequest) => {
      setRoleUpdatingId(roleId);
      setMessage(null);
      setError(null);
      try {
        const response = await adminApi.updateRole(roleId, payload);
        setMessage(labels.roleUpdated);
        showToast(labels.roleUpdated, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setRoleUpdatingId(null);
      }
    },
    [labels.roleUpdated, showToast],
  );
  const deleteRole = useCallback(
    async (roleId: string) => {
      setRoleDeletingId(roleId);
      setMessage(null);
      setError(null);
      try {
        const response = await adminApi.deleteRole(roleId);
        setMessage(labels.roleDeleted);
        showToast(labels.roleDeleted, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setRoleDeletingId(null);
      }
    },
    [labels.roleDeleted, showToast],
  );
  const updateUserStatus = useCallback(
    async (userId: string, isActive: boolean) => {
      setStatusUpdatingUserId(userId);
      setMessage(null);
      setError(null);
      try {
        const response = await adminApi.updateUserStatus(userId, { is_active: isActive });
        setMessage(labels.userStatusUpdated);
        showToast(labels.userStatusUpdated, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setStatusUpdatingUserId(null);
      }
    },
    [labels.userStatusUpdated, showToast],
  );
  const resetUserPassword = useCallback(
    async (userId: string, newPassword: string) => {
      setPasswordResettingUserId(userId);
      setMessage(null);
      setError(null);
      try {
        const response = await adminApi.resetUserPassword(userId, { new_password: newPassword });
        setMessage(labels.userPasswordReset);
        showToast(labels.userPasswordReset, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setPasswordResettingUserId(null);
      }
    },
    [labels.userPasswordReset, showToast],
  );

  return {
    createCostCenter,
    createDepartment,
    createRole,
    createUser,
    deleteCostCenter,
    deleteDepartment,
    deleteRole,
    error,
    message,
    passwordResettingUserId,
    resetUserPassword,
    roleDeletingId,
    roleUpdatingId,
    saving,
    statusUpdatingUserId,
    updateCostCenter,
    updateDepartment,
    updateUser,
    updateRole,
    updateUserStatus,
    userUpdatingId,
  };
}
