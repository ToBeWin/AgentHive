import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { agentModulesApi, licenseApi } from "./license";

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

describe("licenseApi", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getLicenseStatus fetches the license status", async () => {
    const spy = stubFetchReturning(makeResponse({ status: "active", license_type: "pro" }));
    await licenseApi.getLicenseStatus();
    expect(callArgs(spy)[0]).toBe("/api/v1/admin/license/status");
    expect(callInit(spy).method).toBe("GET");
  });

  it("getLicenseModules fetches the license modules", async () => {
    const spy = stubFetchReturning(makeResponse({ modules: [], features: [] }));
    await licenseApi.getLicenseModules();
    expect(callArgs(spy)[0]).toBe("/api/v1/admin/license/modules");
  });

  it("getLicenseActivationRequest fetches the activation request", async () => {
    const spy = stubFetchReturning(makeResponse({ request_code: "abc" }));
    await licenseApi.getLicenseActivationRequest();
    expect(callArgs(spy)[0]).toBe("/api/v1/admin/license/activation-request");
  });

  it("activateLicense posts the activation payload", async () => {
    const payload = { license_key: "lk-1", activation_code: "ac-1" };
    const spy = stubFetchReturning(makeResponse({ status: "active", message: "ok" }));
    await licenseApi.activateLicense(payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/admin/license/activate");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("deactivateLicense posts to the deactivate endpoint", async () => {
    const spy = stubFetchReturning(makeResponse({ status: "inactive", message: "done" }));
    await licenseApi.deactivateLicense();
    expect(callArgs(spy)[0]).toBe("/api/v1/admin/license/deactivate");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify({}));
  });

  it("throws an ApiError on non-2xx responses", async () => {
    stubFetchReturning(makeResponse({ detail: "Invalid license" }, { status: 400 }));
    await expect(licenseApi.activateLicense({ license_key: "bad" })).rejects.toMatchObject({
      status: 400,
      message: "Invalid license",
    });
  });
});

describe("agentModulesApi", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getAgentModules fetches the module list", async () => {
    const spy = stubFetchReturning(makeResponse({ modules: [] }));
    await agentModulesApi.getAgentModules();
    expect(callArgs(spy)[0]).toBe("/api/v1/agent-modules");
    expect(callInit(spy).method).toBe("GET");
  });

  it("installAgentModule posts to the install endpoint with the module id", async () => {
    const spy = stubFetchReturning(makeResponse({ module_id: "m1", state: "installed", message: "ok" }));
    await agentModulesApi.installAgentModule("m1");
    expect(callArgs(spy)[0]).toBe("/api/v1/agent-modules/m1/install");
    expect(callInit(spy).method).toBe("POST");
  });

  it("enableAgentModule posts to the enable endpoint with the module id", async () => {
    const spy = stubFetchReturning(makeResponse({ module_id: "m1", state: "enabled", message: "ok" }));
    await agentModulesApi.enableAgentModule("m1");
    expect(callArgs(spy)[0]).toBe("/api/v1/agent-modules/m1/enable");
    expect(callInit(spy).method).toBe("POST");
  });

  it("disableAgentModule posts to the disable endpoint with the module id", async () => {
    const spy = stubFetchReturning(makeResponse({ module_id: "m1", state: "disabled", message: "ok" }));
    await agentModulesApi.disableAgentModule("m1");
    expect(callArgs(spy)[0]).toBe("/api/v1/agent-modules/m1/disable");
    expect(callInit(spy).method).toBe("POST");
  });

  it("throws an ApiError on non-2xx responses", async () => {
    stubFetchReturning(makeResponse({ detail: "Not licensed" }, { status: 403 }));
    await expect(agentModulesApi.installAgentModule("m1")).rejects.toMatchObject({
      status: 403,
      message: "Not licensed",
    });
  });
});
