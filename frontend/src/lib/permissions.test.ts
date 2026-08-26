import { describe, expect, it } from "vitest";
import type { AuthUser } from "./api";
import { canAccess, canAccessRequirement, filterByPermission, TENANT_ADMIN_PERMISSION } from "./permissions";

function makeUser(overrides: Partial<AuthUser> = {}): AuthUser {
  return {
    user_id: "u1",
    tenant_id: "t1",
    email: "user@example.com",
    name: "User",
    permissions: [],
    is_tenant_admin: false,
    ...overrides,
  } as AuthUser;
}

describe("canAccess", () => {
  it("returns true when no permissions are required", () => {
    expect(canAccess(null)).toBe(true);
    expect(canAccess(makeUser(), undefined, undefined)).toBe(true);
  });

  it("returns false when user is null and permission is required", () => {
    expect(canAccess(null, ["agents:read"])).toBe(false);
  });

  it("short-circuits for tenant admin even without explicit permission", () => {
    const admin = makeUser({ is_tenant_admin: true });
    expect(canAccess(admin, ["agents:write"], ["models:write"])).toBe(true);
  });

  it("short-circuits when tenant.admin permission is present", () => {
    const admin = makeUser({ permissions: [TENANT_ADMIN_PERMISSION] });
    expect(canAccess(admin, ["agents:write"])).toBe(true);
  });

  it("respects requiredAnyPermission (some semantics)", () => {
    const user = makeUser({ permissions: ["agents:read"] });
    expect(canAccess(user, ["agents:read", "agents:write"])).toBe(true);
    expect(canAccess(user, ["agents:write", "models:write"])).toBe(false);
  });

  it("respects requiredAllPermission (every semantics)", () => {
    const user = makeUser({ permissions: ["agents:read", "chat:write"] });
    expect(canAccess(user, undefined, ["agents:read", "chat:write"])).toBe(true);
    expect(canAccess(user, undefined, ["agents:read", "chat:read"])).toBe(false);
  });

  it("combines both requiredAll and requiredAny (AND)", () => {
    const user = makeUser({ permissions: ["agents:read", "chat:write"] });
    expect(canAccess(user, ["agents:read"], ["chat:write"])).toBe(true);
    expect(canAccess(user, ["agents:write"], ["chat:write"])).toBe(false);
  });
});

describe("canAccessRequirement", () => {
  it("returns true when requirement is undefined", () => {
    expect(canAccessRequirement(null)).toBe(true);
  });

  it("delegates to canAccess with both fields", () => {
    const user = makeUser({ permissions: ["agents:read"] });
    expect(canAccessRequirement(user, { requiredAnyPermission: ["agents:read"] })).toBe(true);
    expect(canAccessRequirement(user, { requiredAllPermission: ["agents:write"] })).toBe(false);
  });
});

describe("filterByPermission", () => {
  it("filters items by user permissions", () => {
    const user = makeUser({ permissions: ["agents:read"] });
    const items = [
      { id: "a", requiredAnyPermission: ["agents:read"], workspaces: [] },
      { id: "b", requiredAnyPermission: ["agents:write"], workspaces: [] },
      { id: "c", requiredAllPermission: ["agents:read", "chat:read"], workspaces: [] },
      { id: "d", workspaces: [] }, // no requirement → always visible
    ];
    const filtered = filterByPermission(items, user);
    expect(filtered.map((i) => i.id)).toEqual(["a", "d"]);
  });

  it("returns all items for tenant admin", () => {
    const admin = makeUser({ is_tenant_admin: true });
    const items = [
      { id: "a", requiredAnyPermission: ["agents:read"], workspaces: [] },
      { id: "b", requiredAnyPermission: ["agents:write"], workspaces: [] },
    ];
    const filtered = filterByPermission(items, admin);
    expect(filtered).toHaveLength(2);
  });
});
