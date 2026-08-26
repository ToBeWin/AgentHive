import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { type AuditLogListResponse, adminApi } from "../../lib/api";
import { useAuditLogs } from "./insights";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function auditResponse(id: string): AuditLogListResponse {
  return {
    items: [
      {
        action: `action-${id}`,
        actor_id: null,
        actor_type: "user",
        created_at: "2026-01-01T00:00:00Z",
        details: {},
        id,
        ip_address: null,
        request_id: null,
        resource_id: null,
        resource_type: null,
        status: "success",
        tenant_id: "tenant-1",
        user_agent: null,
      },
    ],
    limit: 50,
    offset: 0,
    total: 1,
  };
}

describe("useAuditLogs request ordering", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("keeps the newest filter result when an older request resolves last", async () => {
    const older = deferred<AuditLogListResponse>();
    const newer = deferred<AuditLogListResponse>();
    const getAuditLogs = vi.spyOn(adminApi, "getAuditLogs").mockImplementation((filters) => {
      return filters?.action === "older" ? older.promise : newer.promise;
    });
    const olderFilters = { action: "older" };
    const newerFilters = { action: "newer" };
    const { result, rerender } = renderHook(({ filters }) => useAuditLogs(filters), {
      initialProps: { filters: olderFilters },
    });

    await waitFor(() => expect(getAuditLogs).toHaveBeenCalledTimes(1));
    rerender({ filters: newerFilters });
    await waitFor(() => expect(getAuditLogs).toHaveBeenCalledTimes(2));

    await act(async () => {
      newer.resolve(auditResponse("newer"));
    });
    await waitFor(() => expect(result.current.data?.items[0]?.id).toBe("newer"));

    await act(async () => {
      older.resolve(auditResponse("older"));
    });
    expect(result.current.data?.items[0]?.id).toBe("newer");
    expect(result.current.loading).toBe(false);
  });

  it("does not commit a pending response after unmount", async () => {
    const pending = deferred<AuditLogListResponse>();
    const getAuditLogs = vi.spyOn(adminApi, "getAuditLogs").mockReturnValue(pending.promise);
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const filters = { action: "pending" };
    const { unmount } = renderHook(() => useAuditLogs(filters));

    await waitFor(() => expect(getAuditLogs).toHaveBeenCalledOnce());
    unmount();
    await act(async () => {
      pending.resolve(auditResponse("late"));
    });

    expect(consoleError).not.toHaveBeenCalled();
  });
});
