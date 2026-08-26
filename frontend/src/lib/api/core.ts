export class ApiError extends Error {
  readonly status: number;
  readonly details: unknown;

  constructor(message: string, status: number, details: unknown = undefined) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.details = details;
  }
}

export interface ApiErrorDetail {
  code?: string;
  message?: string;
  detail?: unknown;
  scope?: string;
  request_id?: string;
  retry_after_seconds?: number;
  limits?: Record<string, number>;
}

declare global {
  interface Window {
    __AGENTHIVE_API_BASE_URL__?: string;
  }
}

export interface AuthUser {
  id: string;
  tenant_id: string;
  email: string;
  full_name: string | null;
  is_tenant_admin: boolean;
  is_super_admin: boolean;
  permissions: string[];
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  user: AuthUser;
}

export interface RequestOptions extends Omit<RequestInit, "body" | "method"> {
  token?: string | null;
}

const AUTH_TOKEN_KEY = "agenthive.access_token";
const API_BASE_URL = window.__AGENTHIVE_API_BASE_URL__ ?? "";
const DEFAULT_API_TIMEOUT_MS = 30_000;
const LARGE_TRANSFER_TIMEOUT_MS = 120_000;
export const SESSION_EXPIRED_EVENT = "agenthive:session-expired";

function requestSignal(callerSignal: AbortSignal | null | undefined, timeoutMs: number) {
  const timeoutSignal = AbortSignal.timeout(timeoutMs);
  return callerSignal ? AbortSignal.any([callerSignal, timeoutSignal]) : timeoutSignal;
}

function getStoredToken() {
  const sessionToken = window.sessionStorage.getItem(AUTH_TOKEN_KEY);
  if (sessionToken) {
    return sessionToken;
  }
  const legacyToken =
    window.localStorage.getItem("agenthive_token") ??
    window.localStorage.getItem("access_token") ??
    window.localStorage.getItem(AUTH_TOKEN_KEY);
  if (legacyToken) {
    window.sessionStorage.setItem(AUTH_TOKEN_KEY, legacyToken);
    const legacyUser = window.localStorage.getItem("agenthive.auth_user");
    const legacyExpiry = window.localStorage.getItem("agenthive.auth_expires_at");
    if (legacyUser) {
      window.sessionStorage.setItem("agenthive.auth_user", legacyUser);
    }
    if (legacyExpiry) {
      window.sessionStorage.setItem("agenthive.auth_expires_at", legacyExpiry);
    }
    removeLegacyPersistentTokens();
  }
  return legacyToken;
}

export function getAuthToken() {
  return getStoredToken();
}

export function hasAuthSession() {
  return Boolean(getStoredToken() || getStoredAuthUser() || getCookie(CSRF_COOKIE_NAME));
}

export function saveAuthToken(auth: AuthTokenResponse) {
  // Browser sessions are transported in an HttpOnly cookie. Keep only display
  // metadata in JavaScript storage; external API clients can still use Bearer tokens.
  window.sessionStorage.removeItem(AUTH_TOKEN_KEY);
  window.sessionStorage.setItem("agenthive.auth_user", JSON.stringify(auth.user));
  window.sessionStorage.setItem("agenthive.auth_expires_at", auth.expires_at);
  removeLegacyPersistentTokens();
}

export function getStoredAuthUser(): AuthUser | null {
  const raw = window.sessionStorage.getItem("agenthive.auth_user");
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function clearAuthToken() {
  window.sessionStorage.removeItem(AUTH_TOKEN_KEY);
  window.sessionStorage.removeItem("agenthive.auth_user");
  window.sessionStorage.removeItem("agenthive.auth_expires_at");
  clearCsrfCookie();
  removeLegacyPersistentTokens();
}

function removeLegacyPersistentTokens() {
  window.localStorage.removeItem(AUTH_TOKEN_KEY);
  window.localStorage.removeItem("agenthive_token");
  window.localStorage.removeItem("access_token");
  window.localStorage.removeItem("agenthive.auth_user");
  window.localStorage.removeItem("agenthive.auth_expires_at");
}

const CSRF_COOKIE_NAME = "agenthive_csrf";

function getCookie(name: string) {
  const prefix = `${encodeURIComponent(name)}=`;
  for (const value of document.cookie.split(";")) {
    const candidate = value.trim();
    if (candidate.startsWith(prefix)) {
      return decodeURIComponent(candidate.slice(prefix.length));
    }
  }
  return null;
}

function clearCsrfCookie() {
  // biome-ignore lint/suspicious/noDocumentCookie: Cookie Store is not supported by all deployed browsers.
  document.cookie = `${encodeURIComponent(CSRF_COOKIE_NAME)}=; Max-Age=0; Path=/; SameSite=Lax`;
}

function applyAuthHeaders(headers: Headers, token: string | null) {
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
    return;
  }
  const csrfToken = getCookie(CSRF_COOKIE_NAME);
  if (csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }
}

function buildUrl(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (!API_BASE_URL) {
    return normalizedPath;
  }
  return `${API_BASE_URL.replace(/\/$/, "")}${normalizedPath}`;
}

async function parseResponse(response: Response) {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  const text = await response.text();
  return text || null;
}

function errorMessage(status: number, payload: unknown) {
  const normalized = extractApiErrorDetail(payload);
  if (normalized?.message) {
    return normalized.message;
  }
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (isApiErrorDetail(detail) && detail.message) {
      return detail.message;
    }
    return `Request failed with status ${status}`;
  }
  if (typeof payload === "string" && payload.trim()) {
    return payload;
  }
  return `Request failed with status ${status}`;
}

function isApiErrorDetail(value: unknown): value is ApiErrorDetail {
  return Boolean(value && typeof value === "object");
}

export function getApiErrorDetail(error: unknown): ApiErrorDetail | null {
  if (!(error instanceof ApiError)) {
    return null;
  }
  const payload = error.details;
  return extractApiErrorDetail(payload);
}

function extractApiErrorDetail(payload: unknown): ApiErrorDetail | null {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  if ("error" in payload) {
    const error = (payload as { error: unknown }).error;
    if (isApiErrorDetail(error)) {
      return error;
    }
  }
  if ("detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (isApiErrorDetail(detail)) {
      return detail;
    }
  }
  return null;
}

function throwApiError(response: Response, payload: unknown, options: RequestOptions): never {
  if (response.status === 401 && options.token !== null && (getStoredToken() || getCookie(CSRF_COOKIE_NAME))) {
    clearAuthToken();
    window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
  }
  throw new ApiError(errorMessage(response.status, payload), response.status, payload);
}

function emitSseChunk(chunk: string, onEvent: (event: string, payload: unknown) => void) {
  const lines = chunk.split("\n");
  const eventLine = lines.find((line) => line.startsWith("event:"));
  const dataLines = lines.filter((line) => line.startsWith("data:")).map((line) => line.replace(/^data:\s?/, ""));
  if (!eventLine || dataLines.length === 0) {
    return;
  }
  const event = eventLine.replace(/^event:\s?/, "").trim();
  const data = dataLines.join("\n");
  try {
    onEvent(event, JSON.parse(data));
  } catch {
    onEvent(event, data);
  }
}

export async function apiGet<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = options.token ?? getStoredToken();
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  applyAuthHeaders(headers, token);

  const response = await fetch(buildUrl(path), {
    ...options,
    credentials: options.credentials ?? "include",
    method: "GET",
    headers,
    signal: requestSignal(options.signal, DEFAULT_API_TIMEOUT_MS),
  });
  const payload = await parseResponse(response);

  if (!response.ok) {
    throwApiError(response, payload, options);
  }

  return payload as T;
}

export async function apiDownloadText(path: string, options: RequestOptions = {}): Promise<string> {
  const token = options.token ?? getStoredToken();
  const headers = new Headers(options.headers);
  headers.set("Accept", "text/csv, application/json, text/plain, */*");
  applyAuthHeaders(headers, token);

  const response = await fetch(buildUrl(path), {
    ...options,
    credentials: options.credentials ?? "include",
    method: "GET",
    headers,
    signal: requestSignal(options.signal, LARGE_TRANSFER_TIMEOUT_MS),
  });
  const text = await response.text();

  if (!response.ok) {
    let payload: unknown = text;
    try {
      payload = JSON.parse(text);
    } catch {
      // Keep non-JSON error bodies as plain text for readable API errors.
    }
    throwApiError(response, payload, options);
  }

  return text;
}

export interface DownloadedBlob {
  blob: Blob;
  filename: string | null;
}

export async function apiDownloadBlob(path: string, options: RequestOptions = {}): Promise<DownloadedBlob> {
  const token = options.token ?? getStoredToken();
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/zip, application/octet-stream, */*");
  applyAuthHeaders(headers, token);

  const response = await fetch(buildUrl(path), {
    ...options,
    credentials: options.credentials ?? "include",
    method: "GET",
    headers,
    signal: requestSignal(options.signal, LARGE_TRANSFER_TIMEOUT_MS),
  });

  if (!response.ok) {
    const payload = await parseResponse(response);
    throwApiError(response, payload, options);
  }

  return {
    blob: await response.blob(),
    filename: parseContentDispositionFilename(response.headers.get("content-disposition")),
  };
}

export async function apiPost<TResponse, TBody>(
  path: string,
  body: TBody,
  options: RequestOptions = {},
): Promise<TResponse> {
  const token = options.token ?? getStoredToken();
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  headers.set("Content-Type", "application/json");
  applyAuthHeaders(headers, token);

  const response = await fetch(buildUrl(path), {
    ...options,
    credentials: options.credentials ?? "include",
    body: JSON.stringify(body),
    method: "POST",
    headers,
    signal: requestSignal(options.signal, DEFAULT_API_TIMEOUT_MS),
  });
  const payload = await parseResponse(response);

  if (!response.ok) {
    throwApiError(response, payload, options);
  }

  return payload as TResponse;
}

export async function apiPostSse<TBody>(
  path: string,
  body: TBody,
  callbacks: { onEvent: (event: string, payload: unknown) => void },
  options: RequestOptions = {},
): Promise<void> {
  const token = options.token ?? getStoredToken();
  const headers = new Headers(options.headers);
  headers.set("Accept", "text/event-stream");
  headers.set("Content-Type", "application/json");
  applyAuthHeaders(headers, token);

  const response = await fetch(buildUrl(path), {
    ...options,
    credentials: options.credentials ?? "include",
    body: JSON.stringify(body),
    method: "POST",
    headers,
  });

  if (!response.ok) {
    const payload = await parseResponse(response);
    throwApiError(response, payload, options);
  }

  if (!response.body) {
    throw new ApiError("Streaming response did not include a readable body.", response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";
    for (const chunk of chunks) {
      emitSseChunk(chunk, callbacks.onEvent);
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    emitSseChunk(buffer, callbacks.onEvent);
  }
}

export async function apiPostForm<TResponse>(
  path: string,
  body: FormData,
  options: RequestOptions = {},
): Promise<TResponse> {
  const token = options.token ?? getStoredToken();
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  applyAuthHeaders(headers, token);

  const response = await fetch(buildUrl(path), {
    ...options,
    credentials: options.credentials ?? "include",
    body,
    method: "POST",
    headers,
    signal: requestSignal(options.signal, LARGE_TRANSFER_TIMEOUT_MS),
  });
  const payload = await parseResponse(response);

  if (!response.ok) {
    throwApiError(response, payload, options);
  }

  return payload as TResponse;
}

export async function apiPut<TResponse, TBody>(
  path: string,
  body: TBody,
  options: RequestOptions = {},
): Promise<TResponse> {
  const token = options.token ?? getStoredToken();
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  headers.set("Content-Type", "application/json");
  applyAuthHeaders(headers, token);

  const response = await fetch(buildUrl(path), {
    ...options,
    credentials: options.credentials ?? "include",
    body: JSON.stringify(body),
    method: "PUT",
    headers,
    signal: requestSignal(options.signal, DEFAULT_API_TIMEOUT_MS),
  });
  const payload = await parseResponse(response);

  if (!response.ok) {
    throwApiError(response, payload, options);
  }

  return payload as TResponse;
}

export async function apiPatch<TResponse, TBody>(
  path: string,
  body: TBody,
  options: RequestOptions = {},
): Promise<TResponse> {
  const token = options.token ?? getStoredToken();
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  headers.set("Content-Type", "application/json");
  applyAuthHeaders(headers, token);

  const response = await fetch(buildUrl(path), {
    ...options,
    credentials: options.credentials ?? "include",
    body: JSON.stringify(body),
    method: "PATCH",
    headers,
    signal: requestSignal(options.signal, DEFAULT_API_TIMEOUT_MS),
  });
  const payload = await parseResponse(response);

  if (!response.ok) {
    throwApiError(response, payload, options);
  }

  return payload as TResponse;
}

export async function apiDelete<TResponse>(path: string, options: RequestOptions = {}): Promise<TResponse> {
  const token = options.token ?? getStoredToken();
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  applyAuthHeaders(headers, token);

  const response = await fetch(buildUrl(path), {
    ...options,
    credentials: options.credentials ?? "include",
    method: "DELETE",
    headers,
    signal: requestSignal(options.signal, DEFAULT_API_TIMEOUT_MS),
  });
  const payload = await parseResponse(response);

  if (!response.ok) {
    throwApiError(response, payload, options);
  }

  return payload as TResponse;
}

function parseContentDispositionFilename(value: string | null) {
  if (!value) {
    return null;
  }
  const utf8Match = value.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1].replace(/"/g, ""));
    } catch {
      return utf8Match[1].replace(/"/g, "");
    }
  }
  const plainMatch = value.match(/filename="?([^";]+)"?/i);
  return plainMatch?.[1] ?? null;
}
