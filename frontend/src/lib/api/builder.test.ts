import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { builderApi } from "./builder";

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

describe("builderApi", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("validate posts the builder config", async () => {
    const config = { name: "Bot", system_prompt: "x", response_style: "formal", language: "zh" } as const;
    const spy = stubFetchReturning(makeResponse({ ok: true, issues: [] }));
    await builderApi.validate(config);
    expect(callArgs(spy)[0]).toBe("/api/v1/agents/builder/validate");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(config));
  });

  it("preview posts the preview request", async () => {
    const config = { name: "Bot", system_prompt: "x", response_style: "formal", language: "zh" } as const;
    const spy = stubFetchReturning(makeResponse({ ok: true, issues: [], rendered: {} }));
    await builderApi.preview({ config });
    expect(callArgs(spy)[0]).toBe("/api/v1/agents/builder/preview");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify({ config }));
  });

  it("createInstance posts the builder config to the instances endpoint", async () => {
    const config = { name: "Bot", system_prompt: "x", response_style: "formal", language: "zh" } as const;
    const spy = stubFetchReturning(makeResponse({ id: "a1", name: "Bot" }));
    await builderApi.createInstance(config);
    expect(callArgs(spy)[0]).toBe("/api/v1/agents/builder/instances");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(config));
  });

  it("updateInstance patches the instance with the agent id in the URL", async () => {
    const config = { name: "Bot", system_prompt: "x", response_style: "formal", language: "zh" } as const;
    const spy = stubFetchReturning(makeResponse({ id: "a1", name: "Bot" }));
    await builderApi.updateInstance("a1", config);
    expect(callArgs(spy)[0]).toBe("/api/v1/agents/builder/instances/a1");
    expect(callInit(spy).method).toBe("PATCH");
    expect(callInit(spy).body).toBe(JSON.stringify(config));
  });

  it("throws an ApiError on non-2xx responses", async () => {
    stubFetchReturning(makeResponse({ detail: "Invalid config" }, { status: 400 }));
    await expect(
      builderApi.validate({ name: "x", system_prompt: "x", response_style: "formal", language: "zh" } as const),
    ).rejects.toMatchObject({ status: 400, message: "Invalid config" });
  });
});
