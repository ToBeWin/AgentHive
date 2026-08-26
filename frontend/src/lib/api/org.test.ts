import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RoleCreateRequest, UserCreateRequest } from "./org";
import { orgApi } from "./org";

type FetchLike = (input: string, init?: RequestInit) => Promise<unknown>;
type FetchMock = ReturnType<typeof vi.fn<FetchLike>>;

function makeResponse(body: unknown, init: ResponseInit = {}): Response {
  const headers = new Headers(init.headers ?? {});
  if (typeof body === "string") {
    if (!headers.has("content-type")) {
      headers.set("content-type", "text/plain");
    }
    return new Response(body, { ...init, headers });
  }
  if (!headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }
  return new Response(JSON.stringify(body), { ...init, headers });
}

function stubFetchReturning(response: unknown): FetchMock {
  const spy = vi.fn<FetchLike>(() => Promise.resolve(response));
  vi.stubGlobal("fetch", spy);
  return spy;
}

function callArgs(spy: FetchMock, index = 0): [string, RequestInit | undefined] {
  return spy.mock.calls[index] as [string, RequestInit | undefined];
}

function callInit(spy: FetchMock, index = 0): RequestInit {
  const init = callArgs(spy, index)[1];
  if (!init) {
    throw new Error("Expected fetch to be called with a RequestInit object");
  }
  return init;
}

describe("orgApi - departments", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getDepartments fetches the department list", async () => {
    const spy = stubFetchReturning(makeResponse({ departments: [], tree: [], total: 0 }));
    await orgApi.getDepartments();
    expect(callArgs(spy)[0]).toBe("/api/v1/orgs/departments");
    expect(callInit(spy).method).toBe("GET");
  });

  it("createDepartment posts the payload", async () => {
    const payload = { name: "Eng", sort_order: 1 } as const;
    const spy = stubFetchReturning(makeResponse({ id: "d1", name: "Eng" }));
    await orgApi.createDepartment(payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/orgs/departments");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("updateDepartment patches the department by id", async () => {
    const payload = { name: "Updated" } as const;
    const spy = stubFetchReturning(makeResponse({ id: "d1" }));
    await orgApi.updateDepartment("d1", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/orgs/departments/d1");
    expect(callInit(spy).method).toBe("PATCH");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("deleteDepartment deletes the department by id", async () => {
    const spy = stubFetchReturning(makeResponse({ id: "d1", deleted: true }));
    await orgApi.deleteDepartment("d1");
    expect(callArgs(spy)[0]).toBe("/api/v1/orgs/departments/d1");
    expect(callInit(spy).method).toBe("DELETE");
  });
});

describe("orgApi - cost centers", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getCostCenters fetches the cost center list", async () => {
    const spy = stubFetchReturning(makeResponse({ cost_centers: [], total: 0 }));
    await orgApi.getCostCenters();
    expect(callArgs(spy)[0]).toBe("/api/v1/orgs/cost-centers");
  });

  it("createCostCenter posts the payload", async () => {
    const payload = { code: "CC1", name: "CC1", is_active: true } as const;
    const spy = stubFetchReturning(makeResponse({ id: "c1" }));
    await orgApi.createCostCenter(payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/orgs/cost-centers");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("updateCostCenter patches the cost center by id", async () => {
    const payload = { name: "Updated" } as const;
    const spy = stubFetchReturning(makeResponse({ id: "c1" }));
    await orgApi.updateCostCenter("c1", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/orgs/cost-centers/c1");
    expect(callInit(spy).method).toBe("PATCH");
  });

  it("deleteCostCenter deletes the cost center by id", async () => {
    const spy = stubFetchReturning(makeResponse({ id: "c1", deleted: true }));
    await orgApi.deleteCostCenter("c1");
    expect(callArgs(spy)[0]).toBe("/api/v1/orgs/cost-centers/c1");
    expect(callInit(spy).method).toBe("DELETE");
  });
});

describe("orgApi - users", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getUsers fetches the user list", async () => {
    const spy = stubFetchReturning(makeResponse({ users: [], total: 0 }));
    await orgApi.getUsers();
    expect(callArgs(spy)[0]).toBe("/api/v1/users");
  });

  it("createUser posts the payload", async () => {
    const payload: UserCreateRequest = {
      email: "u@x.com",
      password: "pw",
      is_tenant_admin: false,
      is_active: true,
      department_bindings: [],
      role_ids: [],
    };
    const spy = stubFetchReturning(makeResponse({ id: "u1" }));
    await orgApi.createUser(payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/users");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("updateUser patches the user by id", async () => {
    const payload = { full_name: "Updated" } as const;
    const spy = stubFetchReturning(makeResponse({ id: "u1" }));
    await orgApi.updateUser("u1", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/users/u1");
    expect(callInit(spy).method).toBe("PATCH");
  });

  it("updateUserStatus patches the status by user id", async () => {
    const payload = { is_active: false } as const;
    const spy = stubFetchReturning(makeResponse({ id: "u1" }));
    await orgApi.updateUserStatus("u1", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/users/u1/status");
    expect(callInit(spy).method).toBe("PATCH");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("resetUserPassword patches the password by user id", async () => {
    const payload = { new_password: "newpw" } as const;
    const spy = stubFetchReturning(makeResponse({ id: "u1" }));
    await orgApi.resetUserPassword("u1", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/users/u1/password");
    expect(callInit(spy).method).toBe("PATCH");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });
});

describe("orgApi - roles", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getRoles fetches the role list", async () => {
    const spy = stubFetchReturning(makeResponse({ roles: [], total: 0 }));
    await orgApi.getRoles();
    expect(callArgs(spy)[0]).toBe("/api/v1/roles");
  });

  it("getRolePermissions fetches the permission catalog", async () => {
    const spy = stubFetchReturning(makeResponse({ permissions: [], total: 0 }));
    await orgApi.getRolePermissions();
    expect(callArgs(spy)[0]).toBe("/api/v1/roles/permissions");
  });

  it("getRolePresets fetches the role presets", async () => {
    const spy = stubFetchReturning(makeResponse({ presets: [], total: 0 }));
    await orgApi.getRolePresets();
    expect(callArgs(spy)[0]).toBe("/api/v1/roles/presets");
  });

  it("createRole posts the payload", async () => {
    const payload: RoleCreateRequest = { name: "R1", permissions: [], is_system: false };
    const spy = stubFetchReturning(makeResponse({ id: "r1" }));
    await orgApi.createRole(payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/roles");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("updateRole patches the role by id", async () => {
    const payload = { name: "Updated" } as const;
    const spy = stubFetchReturning(makeResponse({ id: "r1" }));
    await orgApi.updateRole("r1", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/roles/r1");
    expect(callInit(spy).method).toBe("PATCH");
  });

  it("deleteRole deletes the role by id", async () => {
    const spy = stubFetchReturning(makeResponse({ id: "r1", deleted: true }));
    await orgApi.deleteRole("r1");
    expect(callArgs(spy)[0]).toBe("/api/v1/roles/r1");
    expect(callInit(spy).method).toBe("DELETE");
  });

  it("throws an ApiError on non-2xx responses", async () => {
    stubFetchReturning(makeResponse({ detail: "Forbidden" }, { status: 403 }));
    await expect(orgApi.getRoles()).rejects.toMatchObject({ status: 403, message: "Forbidden" });
  });
});
