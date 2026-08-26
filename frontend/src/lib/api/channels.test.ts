import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { channelsApi } from "./channels";

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

describe("channelsApi", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getChannels fetches the channel list", async () => {
    const spy = stubFetchReturning(makeResponse({ channels: [] }));
    await channelsApi.getChannels();
    expect(callArgs(spy)[0]).toBe("/api/v1/channels");
    expect(callInit(spy).method).toBe("GET");
  });

  it("createChannel posts the channel payload", async () => {
    const payload = {
      name: "WeCom",
      channel_type: "wecom",
      channel_key: "wc1",
      status: "active",
      config: {},
    } as const;
    const spy = stubFetchReturning(makeResponse({ channel: {}, message: "ok" }));
    await channelsApi.createChannel(payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/channels");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("updateChannelStatus patches the status with the channel id in the URL", async () => {
    const payload = { status: "disabled" } as const;
    const spy = stubFetchReturning(makeResponse({ id: "c1", status: "disabled" }));
    await channelsApi.updateChannelStatus("c1", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/channels/c1/status");
    expect(callInit(spy).method).toBe("PATCH");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("testChannel posts the test payload with the channel id in the URL", async () => {
    const payload = { text: "hi", external_user_id: "u1", raw_payload: {} } as const;
    const spy = stubFetchReturning(makeResponse({ ok: true, channel_id: "c1" }));
    await channelsApi.testChannel("c1", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/channels/c1/test");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("pushToChannel posts the push payload with the channel id in the URL", async () => {
    const payload = { external_user_id: "u1", text: "hi", mode: "direct" } as const;
    const spy = stubFetchReturning(makeResponse({ channel_id: "c1", delivered: true }));
    await channelsApi.pushToChannel("c1", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/channels/c1/push");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("throws an ApiError on non-2xx responses", async () => {
    stubFetchReturning(makeResponse({ detail: "Not found" }, { status: 404 }));
    await expect(channelsApi.getChannels()).rejects.toMatchObject({ status: 404, message: "Not found" });
  });
});
