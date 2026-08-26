import type { AuthUser } from "./api";

export const TENANT_ADMIN_PERMISSION = "tenant.admin";

export interface PermissionRequirement {
  requiredAllPermission?: string[];
  requiredAnyPermission?: string[];
}

export function canAccess(user: AuthUser | null, requiredAnyPermission?: string[], requiredAllPermission?: string[]) {
  if (!requiredAnyPermission?.length && !requiredAllPermission?.length) {
    return true;
  }
  if (!user) {
    return false;
  }
  if (user.is_tenant_admin || user.permissions.includes(TENANT_ADMIN_PERMISSION)) {
    return true;
  }
  const hasAll = requiredAllPermission?.every((permission) => user.permissions.includes(permission)) ?? true;
  const hasAny = requiredAnyPermission?.length
    ? requiredAnyPermission.some((permission) => user.permissions.includes(permission))
    : true;
  return hasAll && hasAny;
}

export function canAccessRequirement(user: AuthUser | null, requirement?: PermissionRequirement) {
  return canAccess(user, requirement?.requiredAnyPermission, requirement?.requiredAllPermission);
}

export function filterByPermission<T extends PermissionRequirement>(items: T[], user: AuthUser | null) {
  return items.filter((item) => canAccessRequirement(user, item));
}
