import { BriefcaseBusiness, Building2, Eye, KeyRound, ShieldCheck, UserRound, Wrench } from "lucide-react";

export type RolePreset = {
  key: string;
  icon: typeof ShieldCheck;
  permissions: string[];
  scopeKey: string;
  titleKey: string;
  descriptionKey: string;
};

export const rolePresets: RolePreset[] = [
  {
    key: "enterprise_admin",
    icon: ShieldCheck,
    permissions: ["tenant.admin"],
    scopeKey: "settingsRoleScopeTenant",
    titleKey: "settingsRoleEnterpriseAdmin",
    descriptionKey: "settingsRoleEnterpriseAdminDetail",
  },
  {
    key: "implementation_operator",
    icon: Wrench,
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
    scopeKey: "settingsRoleScopeTenant",
    titleKey: "settingsRoleOps",
    descriptionKey: "settingsRoleOpsDetail",
  },
  {
    key: "model_admin",
    icon: KeyRound,
    permissions: ["models:read", "models:write", "budgets:read", "audit:read"],
    scopeKey: "settingsRoleScopeTenant",
    titleKey: "settingsRoleModelAdmin",
    descriptionKey: "settingsRoleModelAdminDetail",
  },
  {
    key: "agent_admin",
    icon: BriefcaseBusiness,
    permissions: [
      "agents:read",
      "agents:write",
      "chat:read",
      "chat:write",
      "knowledge:read",
      "knowledge:write",
      "channels:read",
    ],
    scopeKey: "settingsRoleScopeDepartment",
    titleKey: "settingsRoleAgentAdmin",
    descriptionKey: "settingsRoleAgentAdminDetail",
  },
  {
    key: "department_leader",
    icon: Building2,
    permissions: [
      "users:read",
      "departments:read",
      "agents:read",
      "chat:read",
      "knowledge:read",
      "budgets:read",
      "analytics:read",
    ],
    scopeKey: "settingsRoleScopeDepartment",
    titleKey: "settingsRoleDepartmentLeader",
    descriptionKey: "settingsRoleDepartmentLeaderDetail",
  },
  {
    key: "employee",
    icon: UserRound,
    permissions: ["agents:read", "chat:read", "chat:write", "knowledge:read"],
    scopeKey: "settingsRoleScopeSelf",
    titleKey: "settingsRoleEmployee",
    descriptionKey: "settingsRoleEmployeeDetail",
  },
  {
    key: "audit_finance",
    icon: Eye,
    permissions: ["budgets:read", "budgets:export", "audit:read", "audit:export", "analytics:read"],
    scopeKey: "settingsRoleScopeTenant",
    titleKey: "settingsRoleAuditFinance",
    descriptionKey: "settingsRoleAuditFinanceDetail",
  },
];

export const governancePermissions = [
  "tenant.admin",
  "users:read",
  "users:write",
  "departments:read",
  "departments:write",
  "agents:read",
  "agents:write",
  "chat:read",
  "chat:write",
  "knowledge:read",
  "knowledge:write",
  "channels:read",
  "channels:write",
  "models:read",
  "models:write",
  "budgets:read",
  "budgets:write",
  "budgets:export",
  "analytics:read",
  "audit:read",
  "audit:export",
  "license:read",
  "license:write",
  "system:diagnostics",
];

export function inferRoleLabel(permissions: string[], t: (key: string) => string) {
  const permissionSet = new Set(permissions);
  if (permissionSet.has("models:write")) {
    return t("settingsRoleModelAdmin");
  }
  if (permissionSet.has("agents:write")) {
    return t("settingsRoleAgentAdmin");
  }
  if (permissionSet.has("system:diagnostics")) {
    return t("settingsRoleOps");
  }
  if (permissionSet.has("audit:export") || permissionSet.has("budgets:export")) {
    return t("settingsRoleAuditFinance");
  }
  if (
    permissionSet.has("analytics:read") &&
    permissionSet.has("budgets:read") &&
    permissionSet.has("users:read") &&
    permissionSet.has("departments:read")
  ) {
    return t("settingsRoleDepartmentLeader");
  }
  if (permissionSet.has("chat:write") || permissionSet.has("agents:read") || permissionSet.has("knowledge:read")) {
    return t("settingsRoleEmployee");
  }
  return t("settingsRoleRestricted");
}
