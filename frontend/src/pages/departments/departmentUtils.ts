import type {
  CostCenterResponse,
  DepartmentResponse,
  DepartmentTreeNode,
  PermissionCatalogItem,
  UserResponse,
} from "../../lib/api";

export type DepartmentFormState = {
  description: string;
  name: string;
};

export type CostCenterFormState = {
  code: string;
  monthlyBudget: string;
  name: string;
};

export type RoleFormState = {
  description: string;
  name: string;
  permissions: string;
  templateKey: string;
};

export type UserFormState = {
  costCenterId: string;
  email: string;
  fullName: string;
  password: string;
  roleId: string;
};

const PERMISSION_CATEGORY_ORDER = [
  "admin",
  "organization",
  "agent",
  "models",
  "budgets",
  "analytics",
  "audit",
  "license",
  "system",
];

export function flattenDepartmentTree(
  nodes: DepartmentTreeNode[],
  depth = 0,
): Array<{ depth: number; node: DepartmentTreeNode }> {
  return nodes.flatMap((node) => [{ depth, node }, ...flattenDepartmentTree(node.children, depth + 1)]);
}

export function userDisplayName(user: UserResponse) {
  return user.full_name || user.username || user.email;
}

export function initials(value: string) {
  return value
    .split(/[.\s@_-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

export function formatUserStatus(user: UserResponse) {
  if (!user.is_active) {
    return "DISABLED";
  }
  return user.is_tenant_admin ? "ADMIN" : "ACTIVE";
}

export function getUserStatusLabelKey(status: string) {
  if (status === "DISABLED") {
    return "departmentsStatusDisabled";
  }
  if (status === "ADMIN") {
    return "departmentsStatusAdmin";
  }
  return "departmentsStatusActive";
}

export function formatDate(value: string | null, locale: string, emptyLabel: string) {
  if (!value) {
    return emptyLabel;
  }
  return new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(value));
}

export function preferredCostCenterForDepartment(
  costCenters: CostCenterResponse[],
  department: DepartmentResponse | null,
) {
  if (!department) {
    return costCenters.find((costCenter) => costCenter.department_id === null) ?? costCenters[0] ?? null;
  }
  return (
    costCenters.find((costCenter) => costCenter.department_id === department.id) ??
    costCenters.find((costCenter) => costCenter.department_id === null) ??
    costCenters[0] ??
    null
  );
}

export function parsePermissionInput(value: string) {
  return value
    .split(",")
    .map((permission) => permission.trim())
    .filter(Boolean);
}

export function formatPermissionInput(permissions: string[]) {
  return Array.from(new Set(permissions)).join(",");
}

export function togglePermissionValue(current: string, permission: string) {
  const values = parsePermissionInput(current);
  const existing = new Set(values);
  if (existing.has(permission)) {
    return formatPermissionInput(values.filter((value) => value !== permission));
  }
  return formatPermissionInput([...values, permission]);
}

export function groupPermissionCatalog(permissions: PermissionCatalogItem[]) {
  const categoryRank = new Map(PERMISSION_CATEGORY_ORDER.map((category, index) => [category, index]));
  const groups = new Map<string, PermissionCatalogItem[]>();

  for (const permission of permissions) {
    const group = groups.get(permission.category) ?? [];
    group.push(permission);
    groups.set(permission.category, group);
  }

  return Array.from(groups, ([category, items]) => ({
    category,
    items: items.slice().sort((a, b) => a.value.localeCompare(b.value)),
  })).sort((a, b) => {
    const rankA = categoryRank.get(a.category) ?? Number.MAX_SAFE_INTEGER;
    const rankB = categoryRank.get(b.category) ?? Number.MAX_SAFE_INTEGER;
    if (rankA !== rankB) {
      return rankA - rankB;
    }
    return a.category.localeCompare(b.category);
  });
}

export function getPermissionCategoryLabelKey(category: string) {
  if (category === "admin") {
    return "departmentsPermissionCategoryAdmin";
  }
  if (category === "organization") {
    return "departmentsPermissionCategoryOrganization";
  }
  if (category === "agent") {
    return "departmentsPermissionCategoryAgent";
  }
  if (category === "models") {
    return "departmentsPermissionCategoryModels";
  }
  if (category === "budgets") {
    return "departmentsPermissionCategoryBudgets";
  }
  if (category === "analytics") {
    return "departmentsPermissionCategoryAnalytics";
  }
  if (category === "audit") {
    return "departmentsPermissionCategoryAudit";
  }
  if (category === "license") {
    return "departmentsPermissionCategoryLicense";
  }
  if (category === "system") {
    return "departmentsPermissionCategorySystem";
  }
  return "departmentsPermissionCategoryOther";
}
