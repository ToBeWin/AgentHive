import { LayoutDashboard } from "lucide-react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { NavItem, PageId, WorkspaceId } from "../data";
import type { AuthUser } from "./api";
import {
  accessibleWorkspaceIds,
  chatConsoleVisible,
  employeeChatPageVisible,
  firstVisiblePage,
  getStoredWorkspacePreference,
  navItemVisibleInWorkspace,
  preferredWorkspace,
  resolveChatNavigationPage,
  saveWorkspacePreference,
  workspaceOrder,
  workspacePageLabelKey,
  workspaceProfile,
} from "./workspaces";

function makeNavItem(overrides: Partial<NavItem> = {}): NavItem {
  return {
    id: "overview" as PageId,
    icon: LayoutDashboard,
    workspaces: ["user", "admin"] as WorkspaceId[],
    ...overrides,
  };
}

function makeUser(permissions: string[] = []): AuthUser {
  return {
    id: "u1",
    email: "test@example.com",
    name: "Test User",
    role: "admin",
    permissions,
    tenant_id: "t1",
    is_active: true,
  } as unknown as AuthUser;
}

describe("workspaceProfile", () => {
  it("returns the profile for the given id", () => {
    expect(workspaceProfile("user").id).toBe("user");
    expect(workspaceProfile("admin").id).toBe("admin");
  });

  it("falls back to the first profile for unknown ids", () => {
    expect(workspaceProfile("unknown" as WorkspaceId).id).toBe("user");
  });
});

describe("workspaceOrder", () => {
  it("contains user and admin in order", () => {
    expect(workspaceOrder).toEqual(["user", "admin"]);
  });
});

describe("accessibleWorkspaceIds", () => {
  it("returns workspaces that have at least one visible nav item", () => {
    const items: NavItem[] = [
      makeNavItem({ id: "overview", workspaces: ["admin"] }),
      makeNavItem({ id: "digitalEmployees", workspaces: ["user"] }),
    ];
    expect(accessibleWorkspaceIds(items)).toEqual(["user", "admin"]);
  });

  it("returns empty array when no items are visible", () => {
    expect(accessibleWorkspaceIds([])).toEqual([]);
  });

  it("respects custom visibility predicate", () => {
    const items: NavItem[] = [
      makeNavItem({ id: "overview", workspaces: ["admin"] }),
      makeNavItem({ id: "digitalEmployees", workspaces: ["user"] }),
    ];
    const result = accessibleWorkspaceIds(items, (_item, ws) => ws === "admin");
    expect(result).toEqual(["admin"]);
  });
});

describe("getStoredWorkspacePreference", () => {
  beforeEach(() => window.localStorage.clear());

  it("returns the stored workspace", () => {
    window.localStorage.setItem("agenthive.active_workspace", "admin");
    expect(getStoredWorkspacePreference()).toBe("admin");
  });

  it("returns null when nothing is stored", () => {
    expect(getStoredWorkspacePreference()).toBeNull();
  });

  it("returns null for invalid stored value", () => {
    window.localStorage.setItem("agenthive.active_workspace", "invalid");
    expect(getStoredWorkspacePreference()).toBeNull();
  });
});

describe("saveWorkspacePreference", () => {
  beforeEach(() => window.localStorage.clear());

  it("stores the workspace id", () => {
    saveWorkspacePreference("admin");
    expect(window.localStorage.getItem("agenthive.active_workspace")).toBe("admin");
  });

  it("does not throw when localStorage is unavailable", () => {
    const original = window.localStorage;
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    });
    expect(() => saveWorkspacePreference("user")).not.toThrow();
    vi.stubGlobal("localStorage", original);
  });
});

describe("preferredWorkspace", () => {
  beforeEach(() => window.localStorage.clear());

  it("returns the stored workspace when accessible", () => {
    window.localStorage.setItem("agenthive.active_workspace", "admin");
    const items: NavItem[] = [makeNavItem({ id: "overview", workspaces: ["admin"] })];
    expect(preferredWorkspace(items)).toBe("admin");
  });

  it("falls back to first accessible when stored is not accessible", () => {
    window.localStorage.setItem("agenthive.active_workspace", "admin");
    const items: NavItem[] = [makeNavItem({ id: "digitalEmployees", workspaces: ["user"] })];
    expect(preferredWorkspace(items)).toBe("user");
  });

  it("returns null when no workspaces are accessible", () => {
    expect(preferredWorkspace([])).toBeNull();
  });
});

describe("workspacePageLabelKey", () => {
  it("returns knowledgeBasesUser for user workspace knowledgeBases", () => {
    expect(workspacePageLabelKey("knowledgeBases", "user")).toBe("knowledgeBasesUser");
  });

  it("returns mediaGenerationUser for user workspace mediaGeneration", () => {
    expect(workspacePageLabelKey("mediaGeneration", "user")).toBe("mediaGenerationUser");
  });

  it("returns admin label for admin workspace", () => {
    expect(workspacePageLabelKey("agents", "admin")).toBe("agentsAdmin");
    expect(workspacePageLabelKey("overview", "admin")).toBe("overviewAdmin");
    expect(workspacePageLabelKey("channels", "admin")).toBe("channelsAdmin");
  });

  it("returns the page id as fallback for admin workspace", () => {
    expect(workspacePageLabelKey("users" as PageId, "admin")).toBe("users");
  });

  it("returns the page id for user workspace non-special pages", () => {
    expect(workspacePageLabelKey("overview", "user")).toBe("overview");
  });
});

describe("navItemVisibleInWorkspace", () => {
  it("returns false when item does not include the workspace", () => {
    const item = makeNavItem({ workspaces: ["admin"] });
    expect(navItemVisibleInWorkspace(item, "user", null, false)).toBe(false);
  });

  it("returns true when item includes the workspace and no permissions required", () => {
    const item = makeNavItem({ workspaces: ["user", "admin"] });
    expect(navItemVisibleInWorkspace(item, "user", null, false)).toBe(true);
  });

  it("returns true in prototype mode regardless of permissions", () => {
    const item = makeNavItem({
      workspaces: ["admin"],
      workspaceRequiredAllPermission: { admin: ["admin.access"] },
    });
    expect(navItemVisibleInWorkspace(item, "admin", null, true)).toBe(true);
  });

  it("checks permissions when required", () => {
    const item = makeNavItem({
      workspaces: ["admin"],
      workspaceRequiredAnyPermission: { admin: ["admin.access"] },
    });
    expect(navItemVisibleInWorkspace(item, "admin", makeUser(["admin.access"]), false)).toBe(true);
    expect(navItemVisibleInWorkspace(item, "admin", makeUser([]), false)).toBe(false);
  });
});

describe("firstVisiblePage", () => {
  it("returns the landing page when visible", () => {
    const items: NavItem[] = [makeNavItem({ id: "digitalEmployees", workspaces: ["user"] })];
    expect(firstVisiblePage(items, "user")).toBe("digitalEmployees");
  });

  it("returns first visible item when landing page is not visible", () => {
    const items: NavItem[] = [
      makeNavItem({ id: "overview", workspaces: ["admin"] }),
      makeNavItem({ id: "agents", workspaces: ["admin"] }),
    ];
    expect(firstVisiblePage(items, "admin")).toBe("overview");
  });

  it("returns the landing page id as fallback", () => {
    expect(firstVisiblePage([], "user")).toBe("digitalEmployees");
  });
});

describe("chatConsoleVisible", () => {
  it("returns true when chat console is visible in any workspace", () => {
    const items: NavItem[] = [makeNavItem({ id: "chatConsole", workspaces: ["user", "admin"] })];
    expect(chatConsoleVisible(items, () => true)).toBe(true);
  });

  it("returns false when chat console nav item does not exist", () => {
    expect(chatConsoleVisible([], () => true)).toBe(false);
  });

  it("returns false when chat console is not visible in any workspace", () => {
    const items: NavItem[] = [makeNavItem({ id: "chatConsole", workspaces: ["user", "admin"] })];
    expect(chatConsoleVisible(items, () => false)).toBe(false);
  });
});

describe("employeeChatPageVisible", () => {
  it("returns true when digital employees is visible in user workspace", () => {
    const items: NavItem[] = [makeNavItem({ id: "digitalEmployees", workspaces: ["user"] })];
    expect(employeeChatPageVisible(items, () => true)).toBe(true);
  });

  it("returns false when digital employees nav item does not exist", () => {
    expect(employeeChatPageVisible([], () => true)).toBe(false);
  });
});

describe("resolveChatNavigationPage", () => {
  it("returns the original page for non-chatConsole pages", () => {
    expect(resolveChatNavigationPage("overview", [], () => true)).toBe("overview");
  });

  it("returns chatConsole when chat console is visible", () => {
    const items: NavItem[] = [makeNavItem({ id: "chatConsole", workspaces: ["admin"] })];
    expect(resolveChatNavigationPage("chatConsole", items, () => true)).toBe("chatConsole");
  });

  it("redirects to digitalEmployees when chat console is not visible but employee chat is", () => {
    const items: NavItem[] = [makeNavItem({ id: "digitalEmployees", workspaces: ["user"] })];
    expect(resolveChatNavigationPage("chatConsole", items, () => true)).toBe("digitalEmployees");
  });

  it("returns chatConsole when neither chat console nor employee chat is visible", () => {
    expect(resolveChatNavigationPage("chatConsole", [], () => true)).toBe("chatConsole");
  });
});
