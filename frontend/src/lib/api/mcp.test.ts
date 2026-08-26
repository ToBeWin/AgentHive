import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mcpApi } from "./mcp";

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

describe("mcpApi", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("listServers fetches the MCP servers list", async () => {
    const servers = [{ id: "s1", name: "Server 1", server_key: "s1" }];
    const spy = stubFetchReturning(makeResponse({ servers }));
    const result = await mcpApi.listServers();
    expect(callArgs(spy)[0]).toBe("/api/v1/mcp/servers");
    expect(callInit(spy).method).toBe("GET");
    expect(result).toEqual({ servers });
  });

  it("throws an ApiError on non-2xx responses", async () => {
    stubFetchReturning(makeResponse({ detail: "Forbidden" }, { status: 403 }));
    await expect(mcpApi.listServers()).rejects.toMatchObject({ status: 403, message: "Forbidden" });
  });
});
