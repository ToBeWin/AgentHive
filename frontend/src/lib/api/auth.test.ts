import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { authApi } from "./auth";

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

describe("authApi", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getSetupStatus fetches setup status without a token", async () => {
    const spy = stubFetchReturning(makeResponse({ initialized: false, setup_available: true }));
    await authApi.getSetupStatus();
    expect(callArgs(spy)[0]).toBe("/api/v1/auth/setup-status");
    expect(callInit(spy).method).toBe("GET");
    expect((callInit(spy).headers as Headers).get("authorization")).toBeNull();
  });

  it("bootstrap posts the tenant bootstrap payload without a token", async () => {
    const payload = {
      tenant_name: "Acme",
      tenant_slug: "acme",
      admin_email: "admin@acme.com",
      admin_password: "pw",
      admin_full_name: "Admin",
    };
    const spy = stubFetchReturning(
      makeResponse({ tenant_id: "t1", admin_user_id: "u1", message: "ok", auth: { access_token: "x" } }),
    );
    await authApi.bootstrap(payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/auth/bootstrap");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
    expect((callInit(spy).headers as Headers).get("authorization")).toBeNull();
  });

  it("login posts credentials without a token", async () => {
    const payload = { tenant_slug: "acme", email: "u@x.com", password: "pw" };
    const spy = stubFetchReturning(makeResponse({ access_token: "tok" }));
    await authApi.login(payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/auth/login");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("refresh posts to the refresh endpoint", async () => {
    const spy = stubFetchReturning(makeResponse({ access_token: "new" }));
    await authApi.refresh();
    expect(callArgs(spy)[0]).toBe("/api/v1/auth/refresh");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify({}));
  });

  it("logout posts to the logout endpoint", async () => {
    const spy = stubFetchReturning(makeResponse({ message: "bye" }));
    await authApi.logout();
    expect(callArgs(spy)[0]).toBe("/api/v1/auth/logout");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify({}));
  });

  it("throws an ApiError on non-2xx responses", async () => {
    stubFetchReturning(makeResponse({ detail: "Invalid credentials" }, { status: 401 }));
    await expect(authApi.login({ tenant_slug: "x", email: "x@x.com", password: "x" })).rejects.toMatchObject({
      status: 401,
      message: "Invalid credentials",
    });
  });
});
