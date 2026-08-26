import type { Locale } from "../../i18n";
import { getStoredLocale, t } from "../../i18n";
import type { ChatMessageResponse, ChatSessionResponse } from "../../lib/api";

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

const RETRY_DELAYS_MS = [200, 600, 1500];
const RETRYABLE_STATUS_CODES = new Set([408, 425, 429, 500, 502, 503, 504]);

export function isRetryableError(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const err = error as { status?: number; name?: string };
  if (typeof err.status === "number") {
    return RETRYABLE_STATUS_CODES.has(err.status);
  }
  // Network errors (fetch failed, timeout) typically have no status; match by name.
  if (err.name === "TypeError" || err.name === "NetworkError" || err.name === "AbortError") {
    return true;
  }
  return false;
}

export async function withRetry<T>(
  fn: () => Promise<T>,
  options: { retries?: number; delays?: number[]; onRetry?: (attempt: number, error: unknown) => void } = {},
): Promise<T> {
  const { retries = RETRY_DELAYS_MS.length, delays = RETRY_DELAYS_MS, onRetry } = options;
  let lastError: unknown;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (attempt === retries || !isRetryableError(error)) {
        throw error;
      }
      onRetry?.(attempt + 1, error);
      const delay = delays[Math.min(attempt, delays.length - 1)];
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
  }
  throw lastError;
}

export function errorToMessage(error: unknown, locale: Locale = getStoredLocale()): string {
  if (!error) return t(locale, "commonErrorUnknown");
  const err = error as { status?: number; message?: string; name?: string };

  // Network errors (fetch failed) — typically TypeError thrown by fetch when
  // the network is unreachable.
  if (err.name === "TypeError" || err.name === "NetworkError") {
    return t(locale, "commonErrorNetwork");
  }
  // Timeout (AbortController / fetch timeout).
  if (err.name === "AbortError") {
    return t(locale, "commonErrorTimeout");
  }
  // HTTP status code classification (ApiError carries a numeric status).
  if (typeof err.status === "number") {
    if (err.status === 401) return t(locale, "commonErrorUnauthorized");
    if (err.status === 403) return t(locale, "commonErrorForbidden");
    if (err.status === 404) return t(locale, "commonErrorNotFound");
    if (err.status === 429) return t(locale, "commonErrorRateLimit");
    if (err.status >= 500) return t(locale, "commonErrorServer");
    if (err.status >= 400) return t(locale, "commonErrorClient");
  }
  return err.message || t(locale, "commonErrorUnknown");
}

export function pendingChatMessage({
  content,
  id,
  role,
  session,
}: {
  content: string;
  id: string;
  role: "assistant" | "user";
  session: ChatSessionResponse;
}): ChatMessageResponse {
  const now = new Date().toISOString();
  return {
    id,
    tenant_id: session.tenant_id,
    conversation_id: session.id,
    role,
    content,
    user_id: null,
    request_id: null,
    model_key: null,
    provider_key: null,
    input_tokens: 0,
    output_tokens: 0,
    total_tokens: 0,
    cost_usd: 0,
    metadata: { local_state: "streaming" },
    created_at: now,
    updated_at: now,
  };
}
