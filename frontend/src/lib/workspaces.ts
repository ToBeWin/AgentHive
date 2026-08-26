import type { NavItem, PageId, WorkspaceId } from "../data";
import type { AuthUser } from "./api";
import { canAccess } from "./permissions";

export interface WorkspaceProfile {
  id: WorkspaceId;
  labelKey: string;
  descriptionKey: string;
  landingPage: PageId;
}

export const workspaceProfiles: WorkspaceProfile[] = [
  {
    id: "user",
    labelKey: "workspaceUser",
    descriptionKey: "workspaceUserDescription",
    landingPage: "digitalEmployees",
  },
  {
    id: "admin",
    labelKey: "workspaceAdmin",
    descriptionKey: "workspaceAdminDescription",
    landingPage: "overview",
  },
];

export const workspaceOrder = workspaceProfiles.map((workspace) => workspace.id);
const workspaceLandingOrder: WorkspaceId[] = ["user", "admin"];
const WORKSPACE_STORAGE_KEY = "agenthive.active_workspace";
type WorkspaceVisibilityPredicate = (item: NavItem, workspace: WorkspaceId) => boolean;

export function workspaceProfile(id: WorkspaceId) {
  return workspaceProfiles.find((workspace) => workspace.id === id) ?? workspaceProfiles[0];
}

export function accessibleWorkspaceIds(navItems: NavItem[], visibleInWorkspace?: WorkspaceVisibilityPredicate) {
  return workspaceOrder.filter((workspace) =>
    navItems.some((item) => itemVisibleInWorkspace(item, workspace, visibleInWorkspace)),
  );
}

export function getStoredWorkspacePreference(): WorkspaceId | null {
  try {
    return workspaceFromString(window.localStorage.getItem(WORKSPACE_STORAGE_KEY));
  } catch {
    return null;
  }
}

export function saveWorkspacePreference(workspace: WorkspaceId) {
  try {
    window.localStorage.setItem(WORKSPACE_STORAGE_KEY, workspace);
  } catch {
    // Browser privacy settings can block localStorage. The in-memory workspace still works.
  }
}

export function preferredWorkspace(navItems: NavItem[], visibleInWorkspace?: WorkspaceVisibilityPredicate) {
  const accessible = accessibleWorkspaceIds(navItems, visibleInWorkspace);
  const stored = getStoredWorkspacePreference();
  if (stored && accessible.includes(stored)) {
    return stored;
  }
  return workspaceLandingOrder.find((workspace) => accessible.includes(workspace)) ?? accessible[0] ?? null;
}

export function workspaceForPage(
  navItems: NavItem[],
  page: PageId,
  currentWorkspace: WorkspaceId,
  visibleInWorkspace?: WorkspaceVisibilityPredicate,
) {
  const target = navItems.find((item) => item.id === page);
  if (!target) {
    return currentWorkspace;
  }
  if (itemVisibleInWorkspace(target, currentWorkspace, visibleInWorkspace)) {
    return currentWorkspace;
  }
  return (
    workspaceLandingOrder.find((workspace) => itemVisibleInWorkspace(target, workspace, visibleInWorkspace)) ??
    workspaceOrder.find((workspace) => itemVisibleInWorkspace(target, workspace, visibleInWorkspace)) ??
    currentWorkspace
  );
}

export function firstVisiblePage(
  navItems: NavItem[],
  workspace: WorkspaceId,
  visibleInWorkspace?: WorkspaceVisibilityPredicate,
) {
  const profile = workspaceProfile(workspace);
  const preferred = navItems.find(
    (item) => item.id === profile.landingPage && itemVisibleInWorkspace(item, workspace, visibleInWorkspace),
  );
  return (
    preferred?.id ??
    navItems.find((item) => itemVisibleInWorkspace(item, workspace, visibleInWorkspace))?.id ??
    profile.landingPage
  );
}

export function workspacePageLabelKey(pageId: PageId, workspaceId: WorkspaceId) {
  if (workspaceId === "user" && pageId === "knowledgeBases") {
    return "knowledgeBasesUser";
  }
  if (workspaceId === "user" && pageId === "mediaGeneration") {
    return "mediaGenerationUser";
  }
  if (workspaceId === "admin") {
    const adminLabels: Partial<Record<PageId, string>> = {
      agentModules: "agentModulesAdmin",
      agents: "agentsAdmin",
      auditLogs: "auditLogsAdmin",
      budgets: "budgetsAdmin",
      channels: "channelsAdmin",
      chatConsole: "chatConsoleAdmin",
      departments: "departmentsAdmin",
      knowledgeBases: "knowledgeBasesAdmin",
      mediaGeneration: "mediaGenerationAdmin",
      models: "modelsAdmin",
      overview: "overviewAdmin",
    };
    return adminLabels[pageId] ?? pageId;
  }
  return pageId;
}

export function navItemVisibleInWorkspace(
  item: NavItem,
  workspaceId: WorkspaceId,
  authUser: AuthUser | null,
  isPrototype: boolean,
) {
  if (!item.workspaces.includes(workspaceId)) {
    return false;
  }
  if (isPrototype) {
    return true;
  }
  const requiredAllPermission = item.workspaceRequiredAllPermission?.[workspaceId];
  const requiredAnyPermission = item.workspaceRequiredAnyPermission?.[workspaceId];
  if (!requiredAllPermission?.length && !requiredAnyPermission?.length) {
    return true;
  }
  return canAccess(authUser, requiredAnyPermission, requiredAllPermission);
}

export function chatConsoleVisible(
  navItems: NavItem[],
  visibleInWorkspace: (item: NavItem, workspace: WorkspaceId) => boolean,
) {
  const chatConsole = navItems.find((item) => item.id === "chatConsole");
  if (!chatConsole) {
    return false;
  }
  return workspaceOrder.some((workspace) => visibleInWorkspace(chatConsole, workspace));
}

export function employeeChatPageVisible(
  navItems: NavItem[],
  visibleInWorkspace: (item: NavItem, workspace: WorkspaceId) => boolean,
) {
  const employeeChat = navItems.find((item) => item.id === "digitalEmployees");
  if (!employeeChat) {
    return false;
  }
  return visibleInWorkspace(employeeChat, "user");
}

/** Route chat-console requests to the employee work surface when trace console is unavailable. */
export function resolveChatNavigationPage(
  pageId: PageId,
  navItems: NavItem[],
  visibleInWorkspace: (item: NavItem, workspace: WorkspaceId) => boolean,
): PageId {
  if (pageId !== "chatConsole") {
    return pageId;
  }
  if (chatConsoleVisible(navItems, visibleInWorkspace)) {
    return pageId;
  }
  if (employeeChatPageVisible(navItems, visibleInWorkspace)) {
    return "digitalEmployees";
  }
  return pageId;
}

function itemVisibleInWorkspace(
  item: NavItem,
  workspace: WorkspaceId,
  visibleInWorkspace?: WorkspaceVisibilityPredicate,
) {
  return visibleInWorkspace ? visibleInWorkspace(item, workspace) : item.workspaces.includes(workspace);
}

function workspaceFromString(value: string | null): WorkspaceId | null {
  if (value === "user" || value === "admin") {
    return value;
  }
  return null;
}
