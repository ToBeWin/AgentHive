import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { auditApi } from "./audit";

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

describe("auditApi", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getAuditLogs fetches logs with default limit and offset", async () => {
    const spy = stubFetchReturning(makeResponse({ items: [], total: 0, limit: 50, offset: 0 }));
    await auditApi.getAuditLogs();
    const url = callArgs(spy)[0];
    expect(url).toContain("/api/v1/audit/logs?");
    expect(url).toContain("limit=50");
    expect(url).toContain("offset=0");
    expect(callInit(spy).method).toBe("GET");
  });

  it("getAuditLogs applies provided filters to the query string", async () => {
    const spy = stubFetchReturning(makeResponse({ items: [], total: 0, limit: 10, offset: 5 }));
    await auditApi.getAuditLogs({ action: "login", status: "success", limit: 10, offset: 5 });
    const url = callArgs(spy)[0];
    expect(url).toContain("action=login");
    expect(url).toContain("status=success");
    expect(url).toContain("limit=10");
    expect(url).toContain("offset=5");
  });

  it("exportAuditLogsCsv downloads the CSV export", async () => {
    const spy = stubFetchReturning(makeResponse("a,b,c\n1,2,3", { headers: { "content-type": "text/csv" } }));
    await auditApi.exportAuditLogsCsv();
    const url = callArgs(spy)[0];
    expect(url).toContain("/api/v1/audit/logs/export?");
    expect(url).not.toContain("offset=");
    expect(callInit(spy).method).toBe("GET");
  });

  it("exportAuditLogsJson downloads the JSON export with format=json", async () => {
    const spy = stubFetchReturning(makeResponse('{"items":[]}'));
    await auditApi.exportAuditLogsJson();
    const url = callArgs(spy)[0];
    expect(url).toContain("/api/v1/audit/logs/export?");
    expect(url).toContain("format=json");
  });

  it("exportAuditLogsCsv uses the provided limit when supplied", async () => {
    const spy = stubFetchReturning(makeResponse("csv"));
    await auditApi.exportAuditLogsCsv({ limit: 100 });
    const url = callArgs(spy)[0];
    expect(url).toContain("limit=100");
  });

  it("throws an ApiError on non-2xx responses", async () => {
    stubFetchReturning(makeResponse({ detail: "Forbidden" }, { status: 403 }));
    await expect(auditApi.getAuditLogs()).rejects.toMatchObject({ status: 403, message: "Forbidden" });
  });
});
