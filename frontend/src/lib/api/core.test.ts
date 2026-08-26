import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AuthTokenResponse, AuthUser } from "./core";
import {
  ApiError,
  apiDelete,
  apiDownloadBlob,
  apiDownloadText,
  apiGet,
  apiPatch,
  apiPost,
  apiPostForm,
  apiPostSse,
  apiPut,
  clearAuthToken,
  getApiErrorDetail,
  getAuthToken,
  getStoredAuthUser,
  hasAuthSession,
  SESSION_EXPIRED_EVENT,
  saveAuthToken,
} from "./core";

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

function makeUser(overrides: Partial<AuthUser> = {}): AuthUser {
  return {
    id: "u1",
    tenant_id: "t1",
    email: "user@example.com",
    full_name: "User",
    is_tenant_admin: false,
    is_super_admin: false,
    permissions: [],
    ...overrides,
  };
}

function makeTokenResponse(overrides: Partial<AuthTokenResponse> = {}): AuthTokenResponse {
  return {
    access_token: "tok-123",
    token_type: "bearer",
    expires_at: "2026-12-31T00:00:00Z",
    user: makeUser(),
    ...overrides,
  };
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

interface SseResponseLike {
  ok: boolean;
  status: number;
  headers: Headers;
  body: { getReader: () => { read: () => Promise<{ done: boolean; value?: Uint8Array }> } };
}

function makeSseResponse(chunks: string[], init: { status?: number; ok?: boolean } = {}): SseResponseLike {
  const encoder = new TextEncoder();
  let index = 0;
  const ok = init.ok ?? true;
  return {
    ok,
    status: init.status ?? 200,
    headers: new Headers({ "content-type": "text/event-stream" }),
    body: {
      getReader: () => ({
        read: async () => {
          if (index < chunks.length) {
            return { done: false, value: encoder.encode(chunks[index++]) };
          }
          return { done: true, value: undefined };
        },
      }),
    },
  };
}

describe("getAuthToken / saveAuthToken / clearAuthToken", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("returns null when no token key is stored", () => {
    expect(getAuthToken()).toBeNull();
  });

  it("does not persist the browser bearer token after saveAuthToken", () => {
    saveAuthToken(makeTokenResponse({ access_token: "tok-123" }));
    expect(getAuthToken()).toBeNull();
    expect(window.sessionStorage.getItem("agenthive.access_token")).toBeNull();
  });

  it("persists the auth user and expiry alongside the token", () => {
    saveAuthToken(
      makeTokenResponse({
        expires_at: "2026-12-31T00:00:00Z",
        user: makeUser({ id: "u9", email: "x@y.com" }),
      }),
    );
    expect(window.sessionStorage.getItem("agenthive.auth_user")).toContain('"u9"');
    expect(window.sessionStorage.getItem("agenthive.auth_expires_at")).toBe("2026-12-31T00:00:00Z");
  });

  it("falls back to the legacy agenthive_token key", () => {
    window.localStorage.setItem("agenthive_token", "legacy-1");
    expect(getAuthToken()).toBe("legacy-1");
    expect(window.sessionStorage.getItem("agenthive.access_token")).toBe("legacy-1");
    expect(window.localStorage.getItem("agenthive_token")).toBeNull();
  });

  it("falls back to the generic access_token key", () => {
    window.localStorage.setItem("access_token", "generic-1");
    expect(getAuthToken()).toBe("generic-1");
  });

  it("clears all known token keys and user fields on clearAuthToken", () => {
    window.sessionStorage.setItem("agenthive.access_token", "a");
    window.localStorage.setItem("agenthive_token", "b");
    window.localStorage.setItem("access_token", "c");
    window.localStorage.setItem("agenthive.auth_user", "{}");
    window.localStorage.setItem("agenthive.auth_expires_at", "x");
    clearAuthToken();
    expect(getAuthToken()).toBeNull();
    expect(window.sessionStorage.getItem("agenthive.auth_user")).toBeNull();
    expect(window.sessionStorage.getItem("agenthive.auth_expires_at")).toBeNull();
  });

  it("recognizes a cookie-backed browser session", () => {
    // biome-ignore lint/suspicious/noDocumentCookie: jsdom has no Cookie Store API.
    document.cookie = "agenthive_csrf=csrf-value; Path=/; SameSite=Lax";
    expect(hasAuthSession()).toBe(true);
  });
});

describe("getStoredAuthUser", () => {
  beforeEach(() => window.localStorage.clear());

  it("returns null when no user is stored", () => {
    expect(getStoredAuthUser()).toBeNull();
  });

  it("parses the stored user JSON into an AuthUser", () => {
    const user = makeUser({ id: "u1", is_tenant_admin: true, permissions: ["x:read"] });
    window.sessionStorage.setItem("agenthive.auth_user", JSON.stringify(user));
    expect(getStoredAuthUser()).toEqual(user);
  });

  it("returns null when the stored JSON is invalid", () => {
    window.sessionStorage.setItem("agenthive.auth_user", "{not json");
    expect(getStoredAuthUser()).toBeNull();
  });
});

describe("apiGet", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("builds a relative URL when no base URL is configured", async () => {
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await apiGet("/agents");
    expect(callArgs(spy)[0]).toBe("/agents");
  });

  it("prepends a leading slash when the path lacks one", async () => {
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await apiGet("agents");
    expect(callArgs(spy)[0]).toBe("/agents");
  });

  it("uses GET as the request method", async () => {
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await apiGet("/agents");
    expect(callInit(spy).method).toBe("GET");
  });

  it("includes cookies by default", async () => {
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await apiGet("/agents");
    expect(callInit(spy).credentials).toBe("include");
  });

  it("applies a default timeout signal to ordinary API requests", async () => {
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await apiGet("/agents");
    expect(callInit(spy).signal).toBeInstanceOf(AbortSignal);
  });

  it("combines caller cancellation with the default timeout", async () => {
    const controller = new AbortController();
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await apiGet("/agents", { signal: controller.signal });
    const signal = callInit(spy).signal as AbortSignal;
    controller.abort();
    expect(signal.aborted).toBe(true);
  });

  it("sets the Accept header to application/json", async () => {
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await apiGet("/agents");
    expect((callInit(spy).headers as Headers).get("accept")).toBe("application/json");
  });

  it("injects the Authorization header from the stored token", async () => {
    window.sessionStorage.setItem("agenthive.access_token", "tok-abc");
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await apiGet("/agents");
    expect((callInit(spy).headers as Headers).get("authorization")).toBe("Bearer tok-abc");
  });

  it("prefers the explicit token option over the stored token", async () => {
    window.sessionStorage.setItem("agenthive.access_token", "stored");
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await apiGet("/agents", { token: "explicit" });
    expect((callInit(spy).headers as Headers).get("authorization")).toBe("Bearer explicit");
  });

  it("falls back to the stored token when token option is null", async () => {
    window.sessionStorage.setItem("agenthive.access_token", "stored");
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await apiGet("/agents", { token: null });
    expect((callInit(spy).headers as Headers).get("authorization")).toBe("Bearer stored");
  });

  it("omits the Authorization header when token option is null and no token is stored", async () => {
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await apiGet("/agents", { token: null });
    expect((callInit(spy).headers as Headers).get("authorization")).toBeNull();
  });

  it("sends the CSRF header when using a cookie-backed session", async () => {
    // biome-ignore lint/suspicious/noDocumentCookie: jsdom has no Cookie Store API.
    document.cookie = "agenthive_csrf=csrf-value; Path=/; SameSite=Lax";
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await apiGet("/agents");
    const headers = callInit(spy).headers as Headers;
    expect(headers.get("authorization")).toBeNull();
    expect(headers.get("x-csrf-token")).toBe("csrf-value");
  });

  it("parses JSON responses into objects", async () => {
    stubFetchReturning(makeResponse({ value: 42 }));
    const result = await apiGet<{ value: number }>("/x");
    expect(result).toEqual({ value: 42 });
  });

  it("returns text content when the response is not JSON", async () => {
    stubFetchReturning(makeResponse("plain text", { headers: { "content-type": "text/plain" } }));
    const result = await apiGet<string>("/x");
    expect(result).toBe("plain text");
  });

  it("returns null when the response body is empty", async () => {
    stubFetchReturning(makeResponse("", { headers: { "content-type": "text/plain" } }));
    const result = await apiGet<string>("/x");
    expect(result).toBeNull();
  });

  it("throws an ApiError with status and message on 4xx", async () => {
    stubFetchReturning(makeResponse({ detail: "Not found" }, { status: 404 }));
    await expect(apiGet("/x")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      message: "Not found",
    });
  });

  it("extracts detail.message when the detail is an object", async () => {
    stubFetchReturning(makeResponse({ detail: { code: "NOT_FOUND", message: "Resource missing" } }, { status: 404 }));
    await expect(apiGet("/x")).rejects.toMatchObject({ message: "Resource missing" });
  });

  it("extracts the standard error envelope message", async () => {
    stubFetchReturning(
      makeResponse(
        { error: { code: "TENANT_SCOPE_DENIED", message: "Tenant scope denied", detail: { scope: "tenant" } } },
        { status: 403 },
      ),
    );
    await expect(apiGet("/x")).rejects.toMatchObject({
      message: "Tenant scope denied",
      status: 403,
    });
  });

  it("falls back to a generic message when the payload has no detail", async () => {
    stubFetchReturning(makeResponse({ unrelated: true }, { status: 500 }));
    await expect(apiGet("/x")).rejects.toMatchObject({
      message: "Request failed with status 500",
      status: 500,
    });
  });

  it("uses the string payload as the message when present", async () => {
    stubFetchReturning(makeResponse("server crashed", { status: 502, headers: { "content-type": "text/plain" } }));
    await expect(apiGet("/x")).rejects.toMatchObject({ message: "server crashed", status: 502 });
  });

  it("clears the token and emits session-expired on 401", async () => {
    window.sessionStorage.setItem("agenthive.access_token", "tok");
    stubFetchReturning(makeResponse({ detail: "expired" }, { status: 401 }));
    const handler = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, handler);
    await expect(apiGet("/x")).rejects.toBeInstanceOf(ApiError);
    expect(window.sessionStorage.getItem("agenthive.access_token")).toBeNull();
    expect(handler).toHaveBeenCalledTimes(1);
    window.removeEventListener(SESSION_EXPIRED_EVENT, handler);
  });

  it("clears a cookie-backed session and emits session-expired on 401", async () => {
    // biome-ignore lint/suspicious/noDocumentCookie: jsdom has no Cookie Store API.
    document.cookie = "agenthive_csrf=csrf-value; Path=/; SameSite=Lax";
    const handler = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, handler);
    stubFetchReturning(makeResponse({ detail: "expired" }, { status: 401 }));

    await expect(apiGet("/x")).rejects.toMatchObject({ status: 401 });

    expect(handler).toHaveBeenCalledTimes(1);
    expect(hasAuthSession()).toBe(false);
    window.removeEventListener(SESSION_EXPIRED_EVENT, handler);
  });

  it("does not emit session-expired when token option is null", async () => {
    window.sessionStorage.setItem("agenthive.access_token", "tok");
    stubFetchReturning(makeResponse({ detail: "expired" }, { status: 401 }));
    const handler = vi.fn();
    window.addEventListener(SESSION_EXPIRED_EVENT, handler);
    await expect(apiGet("/x", { token: null })).rejects.toBeInstanceOf(ApiError);
    expect(handler).not.toHaveBeenCalled();
    expect(window.sessionStorage.getItem("agenthive.access_token")).toBe("tok");
    window.removeEventListener(SESSION_EXPIRED_EVENT, handler);
  });
});

describe("apiPost", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("serializes the body as JSON and sets Content-Type", async () => {
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await apiPost("/agents", { name: "Bot", count: 3 });
    const init = callInit(spy);
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ name: "Bot", count: 3 }));
    expect((init.headers as Headers).get("content-type")).toBe("application/json");
  });

  it("injects the Authorization header when a token is stored", async () => {
    window.sessionStorage.setItem("agenthive.access_token", "tok");
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await apiPost("/agents", { name: "Bot" });
    expect((callInit(spy).headers as Headers).get("authorization")).toBe("Bearer tok");
  });
});

describe("apiPut / apiPatch / apiDelete", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("apiPut sends PUT with a JSON body", async () => {
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await apiPut("/agents/1", { name: "Updated" });
    const init = callInit(spy);
    expect(init.method).toBe("PUT");
    expect(init.body).toBe(JSON.stringify({ name: "Updated" }));
  });

  it("apiPatch sends PATCH with a JSON body", async () => {
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await apiPatch("/agents/1", { status: "active" });
    const init = callInit(spy);
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify({ status: "active" }));
  });

  it("apiDelete sends DELETE without a body", async () => {
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await apiDelete("/agents/1");
    const init = callInit(spy);
    expect(init.method).toBe("DELETE");
    expect(init.body).toBeUndefined();
  });
});

describe("apiPostForm", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("sends FormData without overriding Content-Type", async () => {
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    const form = new FormData();
    form.append("file", "data");
    await apiPostForm("/upload", form);
    const init = callInit(spy);
    expect(init.method).toBe("POST");
    expect(init.body).toBe(form);
    expect((init.headers as Headers).get("content-type")).toBeNull();
  });
});

describe("apiDownloadText", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("returns the raw text body on success", async () => {
    stubFetchReturning(makeResponse("a,b,c\n1,2,3", { headers: { "content-type": "text/csv" } }));
    const result = await apiDownloadText("/export");
    expect(result).toBe("a,b,c\n1,2,3");
  });

  it("parses JSON error bodies for the error message", async () => {
    stubFetchReturning(makeResponse({ detail: "Forbidden" }, { status: 403 }));
    await expect(apiDownloadText("/export")).rejects.toMatchObject({
      status: 403,
      message: "Forbidden",
    });
  });

  it("keeps non-JSON error bodies as plain text in the error message", async () => {
    stubFetchReturning(makeResponse("server crashed", { status: 500, headers: { "content-type": "text/plain" } }));
    await expect(apiDownloadText("/export")).rejects.toMatchObject({
      status: 500,
      message: "server crashed",
    });
  });
});

describe("apiDownloadBlob", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("returns the blob and filename from content-disposition", async () => {
    const blob = new Blob(["binary"], { type: "application/zip" });
    stubFetchReturning(
      new Response(blob, {
        status: 200,
        headers: {
          "content-type": "application/zip",
          "content-disposition": 'attachment; filename="export.zip"',
        },
      }),
    );
    const result = await apiDownloadBlob("/download");
    expect(result.blob).toBeDefined();
    expect(result.blob.type).toBe("application/zip");
    expect(result.blob.size).toBe(13);
    expect(result.filename).toBe("export.zip");
  });

  it("parses UTF-8 encoded filenames from content-disposition", async () => {
    stubFetchReturning(
      new Response(new Blob(["x"]), {
        status: 200,
        headers: { "content-disposition": "attachment; filename*=UTF-8''%E6%8A%A5%E5%91%8A.csv" },
      }),
    );
    const result = await apiDownloadBlob("/download");
    expect(result.filename).toBe("报告.csv");
  });

  it("returns null filename when content-disposition is absent", async () => {
    stubFetchReturning(new Response(new Blob(["x"]), { status: 200 }));
    const result = await apiDownloadBlob("/download");
    expect(result.filename).toBeNull();
  });

  it("throws an ApiError on non-2xx responses", async () => {
    stubFetchReturning(makeResponse({ detail: "Not found" }, { status: 404 }));
    await expect(apiDownloadBlob("/download")).rejects.toMatchObject({ status: 404 });
  });
});

describe("apiPostSse", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("invokes onEvent for each SSE chunk with a parsed JSON payload", async () => {
    stubFetchReturning(
      makeSseResponse(['event: chunk\ndata: {"content":"hello"}\n\n', 'event: end\ndata: {"done":true}\n\n']),
    );
    const onEvent = vi.fn();
    await apiPostSse("/chat", { message: "hi" }, { onEvent });
    expect(onEvent).toHaveBeenCalledTimes(2);
    expect(onEvent.mock.calls[0]).toEqual(["chunk", { content: "hello" }]);
    expect(onEvent.mock.calls[1]).toEqual(["end", { done: true }]);
  });

  it("joins multiple data lines and passes raw text when JSON parsing fails", async () => {
    stubFetchReturning(makeSseResponse(["event: log\ndata: line1\ndata: line2\n\n"]));
    const onEvent = vi.fn();
    await apiPostSse("/chat", { message: "hi" }, { onEvent });
    expect(onEvent.mock.calls[0]).toEqual(["log", "line1\nline2"]);
  });

  it("ignores chunks without an event line", async () => {
    stubFetchReturning(makeSseResponse(['data: {"x":1}\n\n']));
    const onEvent = vi.fn();
    await apiPostSse("/chat", { message: "hi" }, { onEvent });
    expect(onEvent).not.toHaveBeenCalled();
  });

  it("throws an ApiError when the response is not ok", async () => {
    stubFetchReturning(makeResponse({ detail: "no access" }, { status: 403 }));
    await expect(apiPostSse("/chat", { message: "hi" }, { onEvent: vi.fn() })).rejects.toMatchObject({
      status: 403,
    });
  });
});

describe("ApiError", () => {
  it("exposes status, details and message", () => {
    const err = new ApiError("boom", 500, { hint: "x" });
    expect(err).toBeInstanceOf(Error);
    expect(err.name).toBe("ApiError");
    expect(err.message).toBe("boom");
    expect(err.status).toBe(500);
    expect(err.details).toEqual({ hint: "x" });
  });

  it("defaults details to undefined", () => {
    const err = new ApiError("boom", 500);
    expect(err.details).toBeUndefined();
  });
});

describe("getApiErrorDetail", () => {
  it("returns null for non-ApiError values", () => {
    expect(getApiErrorDetail(null)).toBeNull();
    expect(getApiErrorDetail(new Error("plain"))).toBeNull();
  });

  it("returns null when the ApiError has no detail object", () => {
    const err = new ApiError("boom", 500, "some string");
    expect(getApiErrorDetail(err)).toBeNull();
  });

  it("extracts the detail object from an ApiError", () => {
    const err = new ApiError("boom", 400, { detail: { code: "VALIDATION", message: "bad" } });
    expect(getApiErrorDetail(err)).toEqual({ code: "VALIDATION", message: "bad" });
  });

  it("extracts a standard error envelope", () => {
    const err = new ApiError("boom", 403, {
      error: { code: "DENIED", message: "No access", detail: { scope: "department" } },
    });
    expect(getApiErrorDetail(err)).toEqual({
      code: "DENIED",
      message: "No access",
      detail: { scope: "department" },
    });
  });

  it("returns null when the detail is not an object", () => {
    const err = new ApiError("boom", 400, { detail: "string-detail" });
    expect(getApiErrorDetail(err)).toBeNull();
  });
});

describe("base URL handling", () => {
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllGlobals();
    delete (window as { __AGENTHIVE_API_BASE_URL__?: string }).__AGENTHIVE_API_BASE_URL__;
  });

  it("prepends the configured base URL and strips trailing slashes", async () => {
    vi.resetModules();
    (window as { __AGENTHIVE_API_BASE_URL__?: string }).__AGENTHIVE_API_BASE_URL__ = "https://api.test/";
    const mod = await import("./core");
    const spy = vi.fn<FetchLike>(() => Promise.resolve(makeResponse({ ok: true })));
    vi.stubGlobal("fetch", spy);
    await mod.apiGet("/agents");
    expect(callArgs(spy)[0]).toBe("https://api.test/agents");
  });
});
