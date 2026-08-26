import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./core";
import { systemApi } from "./system";

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

describe("systemApi", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getHealth fetches the health report", async () => {
    const report = { status: "healthy", service: "agenthive", version: "1.0", environment: "prod", checked_at: "x" };
    const spy = stubFetchReturning(makeResponse(report));
    const result = await systemApi.getHealth();
    expect(callArgs(spy)[0]).toBe("/api/v1/health");
    expect(callInit(spy).method).toBe("GET");
    expect(result).toMatchObject({ status: "healthy", service: "agenthive" });
  });

  it("getInfo fetches system info", async () => {
    const spy = stubFetchReturning(makeResponse({ name: "AgentHive", edition: "oss", version: "1.0" }));
    await systemApi.getInfo();
    expect(callArgs(spy)[0]).toBe("/api/v1/system/info");
    expect(callInit(spy).method).toBe("GET");
  });

  it("getDiagnostics fetches the diagnostics report", async () => {
    const spy = stubFetchReturning(
      makeResponse({ product: "AgentHive", report_type: "deployment_diagnostics", schema_version: "1" }),
    );
    await systemApi.getDiagnostics();
    expect(callArgs(spy)[0]).toBe("/api/v1/system/diagnostics");
    expect(callInit(spy).method).toBe("GET");
  });

  it("getSupportBundle downloads a blob", async () => {
    const spy = vi.fn<FetchLike>(() =>
      Promise.resolve(
        new Response(new Blob(["zip"], { type: "application/zip" }), {
          status: 200,
          headers: { "content-disposition": 'attachment; filename="bundle.zip"' },
        }),
      ),
    );
    vi.stubGlobal("fetch", spy);
    const result = await systemApi.getSupportBundle();
    expect(callArgs(spy)[0]).toBe("/api/v1/system/support-bundle");
    expect(callInit(spy).method).toBe("GET");
    expect(result.filename).toBe("bundle.zip");
    expect(result.blob.size).toBeGreaterThan(0);
  });

  it("getReadiness returns the health report on success", async () => {
    const report = {
      status: "healthy",
      service: "agenthive",
      version: "1.0",
      environment: "prod",
      checked_at: "x",
      components: {},
    };
    const spy = stubFetchReturning(makeResponse(report));
    const result = await systemApi.getReadiness();
    expect(callArgs(spy)[0]).toBe("/api/v1/health/readiness");
    expect(result).toMatchObject({ status: "healthy" });
  });

  it("getReadiness returns the health report from ApiError details when degraded", async () => {
    const report = {
      status: "degraded",
      service: "agenthive",
      version: "1.0",
      environment: "prod",
      checked_at: "x",
      components: {},
    };
    stubFetchReturning(makeResponse(report, { status: 503 }));
    const result = await systemApi.getReadiness();
    expect(result).toMatchObject({ status: "degraded" });
  });

  it("getReadiness rethrows non-ApiError errors", async () => {
    stubFetchReturning(makeResponse("server crashed", { status: 500, headers: { "content-type": "text/plain" } }));
    await expect(systemApi.getReadiness()).rejects.toBeInstanceOf(ApiError);
  });

  it("throws an ApiError on non-2xx responses for getHealth", async () => {
    stubFetchReturning(makeResponse({ detail: "down" }, { status: 503 }));
    await expect(systemApi.getHealth()).rejects.toMatchObject({ status: 503, message: "down" });
  });
});
