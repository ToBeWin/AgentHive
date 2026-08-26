import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { analyticsApi } from "./analytics";

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

describe("analyticsApi", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getAnalyticsOverview fetches the analytics overview", async () => {
    const overview = {
      totals: { total_requests: 10, total_tokens: 100, total_cost_usd: 1.5, success_rate: 0.9 },
      model_usage: [],
      daily_usage: [],
      department_usage: [],
      user_usage: [],
      agent_usage: [],
      generated_at: "2026-01-01T00:00:00Z",
      metadata: {},
    };
    const spy = stubFetchReturning(makeResponse(overview));
    const result = await analyticsApi.getAnalyticsOverview();
    expect(callArgs(spy)[0]).toBe("/api/v1/analytics/overview");
    expect(callInit(spy).method).toBe("GET");
    expect(result).toEqual(overview);
  });

  it("throws an ApiError on non-2xx responses", async () => {
    stubFetchReturning(makeResponse({ detail: "Internal error" }, { status: 500 }));
    await expect(analyticsApi.getAnalyticsOverview()).rejects.toMatchObject({
      status: 500,
      message: "Internal error",
    });
  });
});
