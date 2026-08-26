import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { chatApi } from "./chat";

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

describe("chatApi", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getChatSessions fetches the session list", async () => {
    const spy = stubFetchReturning(makeResponse({ sessions: [], total: 0, limit: 20, offset: 0 }));
    await chatApi.getChatSessions();
    expect(callArgs(spy)[0]).toBe("/api/v1/chat/sessions?limit=20");
    expect(callInit(spy).method).toBe("GET");
  });

  it("createChatSession posts the session payload", async () => {
    const payload = { source: "web" } as const;
    const spy = stubFetchReturning(makeResponse({ id: "s1", title: "t", source: "web" }));
    await chatApi.createChatSession(payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/chat/sessions");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("getChatMessages fetches messages for the session id", async () => {
    const spy = stubFetchReturning(makeResponse({ messages: [] }));
    await chatApi.getChatMessages("s1");
    expect(callArgs(spy)[0]).toBe("/api/v1/chat/sessions/s1/messages");
    expect(callInit(spy).method).toBe("GET");
  });

  it("sendChatMessage posts the message payload with the session id in the URL", async () => {
    const payload = { content: "hi" } as const;
    const spy = stubFetchReturning(makeResponse({ request_id: "r1" }));
    await chatApi.sendChatMessage("s1", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/chat/sessions/s1/messages");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("throws an ApiError on non-2xx responses", async () => {
    stubFetchReturning(makeResponse({ detail: "Not found" }, { status: 404 }));
    await expect(chatApi.getChatMessages("s1")).rejects.toMatchObject({ status: 404, message: "Not found" });
  });
});

function makeSseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  });
}

function sseEvent(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

describe("chatApi.streamChatMessage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("invokes onMetadata callback for metadata events", async () => {
    const metadataPayload = {
      user_message: { id: "m1", tenant_id: "t1", conversation_id: "c1", role: "user", content: "hi" },
      request_id: "r1",
      provider_key: "openai",
      model_key: "gpt-4",
      usage: { total_tokens: 10, input_tokens: 5, output_tokens: 5, cost_usd: "0.001" },
      metadata: {},
    };
    const spy = vi.fn(() => Promise.resolve(makeSseResponse([sseEvent("metadata", metadataPayload)])));
    vi.stubGlobal("fetch", spy);

    const onMetadata = vi.fn();
    await chatApi.streamChatMessage("s1", { content: "hi" }, { onMetadata });
    expect(onMetadata).toHaveBeenCalledWith(expect.objectContaining({ request_id: "r1" }));
  });

  it("invokes onDelta callback for delta events", async () => {
    const spy = vi.fn(() => Promise.resolve(makeSseResponse([sseEvent("delta", { content: "hello" })])));
    vi.stubGlobal("fetch", spy);

    const onDelta = vi.fn();
    await chatApi.streamChatMessage("s1", { content: "hi" }, { onDelta });
    expect(onDelta).toHaveBeenCalledWith({ content: "hello" });
  });

  it("invokes onStatus callback for status events", async () => {
    const spy = vi.fn(() =>
      Promise.resolve(makeSseResponse([sseEvent("status", { stage: "accepted", state: "started" })])),
    );
    vi.stubGlobal("fetch", spy);

    const onStatus = vi.fn();
    await chatApi.streamChatMessage("s1", { content: "hi" }, { onStatus });
    expect(onStatus).toHaveBeenCalledWith({ stage: "accepted", state: "started" });
  });

  it("invokes onDone callback for done events", async () => {
    const spy = vi.fn(() => Promise.resolve(makeSseResponse([sseEvent("done", { message_id: "m2" })])));
    vi.stubGlobal("fetch", spy);

    const onDone = vi.fn();
    await chatApi.streamChatMessage("s1", { content: "hi" }, { onDone });
    expect(onDone).toHaveBeenCalledWith({ message_id: "m2" });
  });

  it("invokes onError callback for error events", async () => {
    const spy = vi.fn(() =>
      Promise.resolve(makeSseResponse([sseEvent("error", { status: 500, detail: { message: "Internal error" } })])),
    );
    vi.stubGlobal("fetch", spy);

    const onError = vi.fn();
    await chatApi.streamChatMessage("s1", { content: "hi" }, { onError });
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ status: 500 }));
  });

  it("handles error events with non-object detail", async () => {
    const spy = vi.fn(() =>
      Promise.resolve(makeSseResponse([sseEvent("error", { status: 403, detail: "Forbidden" })])),
    );
    vi.stubGlobal("fetch", spy);

    const onError = vi.fn();
    await chatApi.streamChatMessage("s1", { content: "hi" }, { onError });
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ status: 403, detail: "Forbidden" }));
  });

  it("ignores malformed event payloads", async () => {
    const malformedMetadata = `event: metadata\ndata: {"not_user_message": true}\n\n`;
    const malformedDelta = `event: delta\ndata: {"not_content": true}\n\n`;
    const malformedStatus = `event: status\ndata: {"not_stage": true}\n\n`;
    const malformedDone = `event: done\ndata: {"not_message_id": true}\n\n`;
    const malformedError = `event: error\ndata: {"not_status": true}\n\n`;

    const spy = vi.fn(() =>
      Promise.resolve(
        makeSseResponse([malformedMetadata, malformedDelta, malformedStatus, malformedDone, malformedError]),
      ),
    );
    vi.stubGlobal("fetch", spy);

    const onMetadata = vi.fn();
    const onDelta = vi.fn();
    const onStatus = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    await chatApi.streamChatMessage("s1", { content: "hi" }, { onMetadata, onDelta, onStatus, onDone, onError });
    expect(onMetadata).not.toHaveBeenCalled();
    expect(onDelta).not.toHaveBeenCalled();
    expect(onStatus).not.toHaveBeenCalled();
    expect(onDone).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });

  it("passes abort signal to fetch", async () => {
    const spy = vi.fn<FetchLike>(() => Promise.resolve(makeSseResponse([sseEvent("done", { message_id: "m3" })])));
    vi.stubGlobal("fetch", spy);

    const controller = new AbortController();
    await chatApi.streamChatMessage("s1", { content: "hi" }, {}, { signal: controller.signal });
    expect(callInit(spy).signal).toBe(controller.signal);
  });

  it("sends POST request with correct URL and body", async () => {
    const spy = vi.fn<FetchLike>(() => Promise.resolve(makeSseResponse([sseEvent("done", { message_id: "m4" })])));
    vi.stubGlobal("fetch", spy);

    const payload = { content: "test message" };
    await chatApi.streamChatMessage("s1", payload, {});
    expect(callArgs(spy)[0]).toBe("/api/v1/chat/sessions/s1/messages/stream");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });
});
