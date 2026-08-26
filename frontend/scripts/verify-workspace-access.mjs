import { readFileSync } from "node:fs";
import { readStylesSource } from "./read-styles.mjs";

const navSource = readFileSync(new URL("../src/data.ts", import.meta.url), "utf8");
const rolesSource = readFileSync(new URL("../src/pages/settings/roleWorkspaceData.ts", import.meta.url), "utf8");
const commandCenterSource = readFileSync(
  new URL("../src/components/layout/WorkspaceCommandCenter.tsx", import.meta.url),
  "utf8",
);
const messagesSource = readFileSync(new URL("../src/i18n/messages/common.ts", import.meta.url), "utf8");
const zhMessagesSource = readFileSync(new URL("../src/i18n/messages/common.zh.ts", import.meta.url), "utf8");
const stylesSource = readStylesSource();

const workspaceOrder = ["user", "admin"];
const workspaceLandingOrder = ["user", "admin"];
const navItems = parseNavItems(navSource);
const rolePresets = parseRolePresets(rolesSource);

const assertions = [
  {
    key: "employee",
    visiblePages: ["digitalEmployees", "mediaGeneration", "knowledgeBases"],
    forbiddenPages: ["chatConsole"],
    workspaces: ["user"],
    preferredWorkspace: "user",
  },
  {
    key: "agent_admin",
    mustIncludePages: ["digitalEmployees", "agents", "agentModules", "knowledgeBases", "mediaGeneration", "channels"],
    forbiddenPages: ["chatConsole"],
    mustIncludeWorkspaces: ["user", "admin"],
    preferredWorkspace: "user",
  },
  {
    key: "implementation_operator",
    mustIncludePages: ["digitalEmployees", "channels", "auditLogs", "license", "settings"],
    forbiddenPages: ["mediaGeneration", "departments", "models"],
    mustIncludeWorkspaces: ["user", "admin"],
  },
  {
    key: "model_admin",
    mustIncludePages: ["models", "budgets", "auditLogs"],
    forbiddenPages: [
      "digitalEmployees",
      "chatConsole",
      "agents",
      "agentModules",
      "knowledgeBases",
      "mediaGeneration",
      "departments",
      "channels",
      "license",
      "settings",
    ],
    workspaces: ["admin"],
    preferredWorkspace: "admin",
  },
  {
    key: "department_leader",
    mustIncludePages: ["digitalEmployees", "knowledgeBases", "overview", "budgets"],
    forbiddenPages: ["chatConsole", "agents", "agentModules", "mediaGeneration", "departments", "license", "settings"],
    mustIncludeWorkspaces: ["user", "admin"],
    preferredWorkspace: "user",
  },
  {
    key: "audit_finance",
    mustIncludePages: ["overview", "budgets", "auditLogs"],
    forbiddenPages: ["digitalEmployees", "agents", "agentModules", "knowledgeBases"],
    workspaces: ["admin"],
    preferredWorkspace: "admin",
  },
];

for (const assertion of assertions) {
  const role = rolePresets.find((item) => item.key === assertion.key);
  invariant(role, `Missing role preset: ${assertion.key}`);
  const permissionSet = new Set(role.permissions);
  const visible = visibleNavItems(permissionSet);
  const pages = visible.map((item) => item.id);
  const workspaces = accessibleWorkspaceIds(visible, permissionSet);
  const preferred = preferredWorkspace(visible, permissionSet);

  if (assertion.visiblePages) {
    assertArrayEqual(pages, assertion.visiblePages, `${assertion.key} visible pages`);
  }
  if (assertion.workspaces) {
    assertArrayEqual(workspaces, assertion.workspaces, `${assertion.key} workspaces`);
  }
  if (assertion.preferredWorkspace) {
    invariant(
      preferred === assertion.preferredWorkspace,
      `${assertion.key} preferred workspace expected ${assertion.preferredWorkspace}, got ${preferred}`,
    );
  }
  for (const page of assertion.mustIncludePages ?? []) {
    invariant(pages.includes(page), `${assertion.key} should include page ${page}. Actual: ${pages.join(", ")}`);
  }
  for (const page of assertion.forbiddenPages ?? []) {
    invariant(!pages.includes(page), `${assertion.key} should not include page ${page}. Actual: ${pages.join(", ")}`);
  }
  for (const workspace of assertion.mustIncludeWorkspaces ?? []) {
    invariant(
      workspaces.includes(workspace),
      `${assertion.key} should include workspace ${workspace}. Actual: ${workspaces.join(", ")}`,
    );
  }
}

invariant(
  commandCenterSource.includes("storedCommandCenterCollapsed(activeWorkspace)") &&
    commandCenterSource.includes("return true") &&
    commandCenterSource.includes("workspace-command-toggle") &&
    commandCenterSource.includes("workspace-command-list") &&
    commandCenterSource.includes("!collapsed &&"),
  "Workspace command center must be collapsible and default collapsed for the employee workspace.",
);
invariant(
  stylesSource.includes(".workspace-command-center.collapsed") &&
    stylesSource.includes(".workspace-command-toggle") &&
    stylesSource.includes(".workspace-command-copy small"),
  "Workspace command center collapsed styles are missing.",
);

const commandCenterMessageKeys = [
  "workspaceCommandShortcutsCount",
  "workspaceCommandExpand",
  "workspaceCommandCollapse",
];
for (const key of commandCenterMessageKeys) {
  invariant(
    countMessageKey(messagesSource, key) === 1 && countMessageKey(zhMessagesSource, key) === 1,
    `Missing localized workspace command center key: ${key}`,
  );
}

console.log("Workspace access verification passed.");

function visibleNavItems(permissionSet) {
  const isTenantAdmin = permissionSet.has("tenant.admin");
  return navItems.filter((item) => {
    const globallyVisible = isTenantAdmin || hasGlobalPermission(item, permissionSet);
    return globallyVisible && item.workspaces.some((workspace) => itemVisibleInWorkspace(item, workspace, permissionSet));
  });
}

function hasGlobalPermission(item, permissionSet) {
  const hasAll = item.requiredAllPermission.every((permission) => permissionSet.has(permission));
  const hasAny = item.requiredAnyPermission.length
    ? item.requiredAnyPermission.some((permission) => permissionSet.has(permission))
    : true;
  return hasAll && hasAny;
}

function accessibleWorkspaceIds(items, permissionSet) {
  return workspaceOrder.filter((workspace) =>
    items.some((item) => itemVisibleInWorkspace(item, workspace, permissionSet)),
  );
}

function preferredWorkspace(items, permissionSet) {
  const accessible = accessibleWorkspaceIds(items, permissionSet);
  return workspaceLandingOrder.find((workspace) => accessible.includes(workspace)) ?? accessible[0] ?? null;
}

function itemVisibleInWorkspace(item, workspace, permissionSet) {
  if (!item.workspaces.includes(workspace)) {
    return false;
  }
  if (permissionSet.has("tenant.admin")) {
    return true;
  }
  const requiredAllPermission = item.workspaceRequiredAllPermission[workspace] ?? [];
  const requiredAnyPermission = item.workspaceRequiredAnyPermission[workspace] ?? [];
  if (!requiredAllPermission.length && !requiredAnyPermission.length) {
    return true;
  }
  return (
    requiredAllPermission.every((permission) => permissionSet.has(permission)) &&
    (!requiredAnyPermission.length || requiredAnyPermission.some((permission) => permissionSet.has(permission)))
  );
}

function parseNavItems(source) {
  const arrayBody = extractArrayBody(source, "navItems");
  return splitTopLevelObjects(arrayBody).map((objectSource) => ({
    id: requiredStringProperty(objectSource, "id"),
    requiredAllPermission: stringArrayProperty(objectSource, "requiredAllPermission"),
    requiredAnyPermission: stringArrayProperty(objectSource, "requiredAnyPermission"),
    workspaceRequiredAllPermission: workspacePermissionProperty(objectSource, "workspaceRequiredAllPermission"),
    workspaceRequiredAnyPermission: workspacePermissionProperty(objectSource, "workspaceRequiredAnyPermission"),
    workspaces: stringArrayProperty(objectSource, "workspaces"),
  }));
}

function workspacePermissionProperty(source, name) {
  const start = source.indexOf(`${name}:`);
  if (start === -1) {
    return {};
  }
  const braceStart = source.indexOf("{", start);
  if (braceStart === -1) {
    return {};
  }
  let depth = 0;
  for (let index = braceStart; index < source.length; index += 1) {
    const char = source[index];
    if (char === "{") {
      depth += 1;
    }
    if (char === "}") {
      depth -= 1;
      if (depth === 0) {
        const body = source.slice(braceStart + 1, index);
        return Object.fromEntries(
          [...body.matchAll(/(user|admin|ops):\s*\[([^\]]*)\]/g)].map((match) => [
            match[1],
            [...match[2].matchAll(/"([^"]+)"/g)].map((item) => item[1]),
          ]),
        );
      }
    }
  }
  return {};
}

function parseRolePresets(source) {
  const arrayBody = extractArrayBody(source, "rolePresets");
  return splitTopLevelObjects(arrayBody).map((objectSource) => ({
    key: requiredStringProperty(objectSource, "key"),
    permissions: stringArrayProperty(objectSource, "permissions"),
  }));
}

function extractArrayBody(source, name) {
  const assignment = source.indexOf(`const ${name}`);
  invariant(assignment !== -1, `Unable to find ${name}`);
  const equals = source.indexOf("=", assignment);
  invariant(equals !== -1, `Unable to find ${name} assignment`);
  const start = source.indexOf("[", equals);
  invariant(start !== -1, `Unable to find ${name} array start`);
  let depth = 0;
  for (let index = start; index < source.length; index += 1) {
    const char = source[index];
    if (char === "[") {
      depth += 1;
    }
    if (char === "]") {
      depth -= 1;
      if (depth === 0) {
        return source.slice(start + 1, index);
      }
    }
  }
  throw new Error(`Unable to find ${name} array end`);
}

function splitTopLevelObjects(source) {
  const objects = [];
  let depth = 0;
  let start = -1;
  for (let index = 0; index < source.length; index += 1) {
    const char = source[index];
    if (char === "{") {
      if (depth === 0) {
        start = index;
      }
      depth += 1;
    }
    if (char === "}") {
      depth -= 1;
      if (depth === 0 && start !== -1) {
        objects.push(source.slice(start, index + 1));
        start = -1;
      }
    }
  }
  return objects;
}

function requiredStringProperty(source, name) {
  const match = source.match(new RegExp(`${name}:\\s*"([^"]+)"`));
  invariant(match, `Missing string property ${name}`);
  return match[1];
}

function stringArrayProperty(source, name) {
  const match = source.match(new RegExp(`${name}:\\s*\\[([^\\]]*)\\]`));
  if (!match) {
    return [];
  }
  return [...match[1].matchAll(/"([^"]+)"/g)].map((item) => item[1]);
}

function assertArrayEqual(actual, expected, label) {
  invariant(
    JSON.stringify(actual) === JSON.stringify(expected),
    `${label} expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`,
  );
}

function countMessageKey(source, key) {
  return [...source.matchAll(new RegExp(`\\b${key}:`, "g"))].length;
}

function invariant(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}
