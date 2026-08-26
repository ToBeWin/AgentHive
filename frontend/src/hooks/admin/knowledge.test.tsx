import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  adminApi,
  type KnowledgeDocumentListResponse,
  type KnowledgeDocumentResponse,
  type WorkbenchKnowledgeDocumentListResponse,
  type WorkbenchKnowledgeDocumentResponse,
} from "../../lib/api";
import { useKnowledgeDocuments, useWorkbenchKnowledgeDocuments } from "./knowledge";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

function knowledgeDocument(baseId: string): KnowledgeDocumentResponse {
  return {
    checksum_sha256: null,
    chunk_count: 1,
    content_type: "text/plain",
    created_at: "2026-01-01T00:00:00Z",
    error_message: null,
    filename: `${baseId}.txt`,
    id: `document-${baseId}`,
    knowledge_base_id: baseId,
    metadata: {},
    rag_document_id: null,
    size_bytes: 10,
    source: "api_upload",
    status: "indexed",
    storage_bucket: "knowledge",
    storage_object_key: `${baseId}.txt`,
    tenant_id: "tenant-1",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

function workbenchDocument(baseId: string): WorkbenchKnowledgeDocumentResponse {
  return {
    chunk_count: 1,
    content_type: "text/plain",
    filename: `${baseId}.txt`,
    id: `workbench-document-${baseId}`,
    knowledge_base_id: baseId,
    size_bytes: 10,
    source: "api_upload",
    status: "indexed",
    updated_at: "2026-01-01T00:00:00Z",
  };
}

describe("knowledge document request ordering", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("keeps documents for the latest admin knowledge base", async () => {
    const older = deferred<KnowledgeDocumentListResponse>();
    const newer = deferred<KnowledgeDocumentListResponse>();
    const getKnowledgeDocuments = vi.spyOn(adminApi, "getKnowledgeDocuments").mockImplementation((baseId) => {
      return baseId === "older" ? older.promise : newer.promise;
    });
    const { result, rerender } = renderHook(({ baseId }) => useKnowledgeDocuments(baseId), {
      initialProps: { baseId: "older" as string | null },
    });

    await waitFor(() => expect(getKnowledgeDocuments).toHaveBeenCalledTimes(1));
    rerender({ baseId: "newer" });
    await waitFor(() => expect(getKnowledgeDocuments).toHaveBeenCalledTimes(2));

    await act(async () => {
      newer.resolve({ documents: [knowledgeDocument("newer")] });
    });
    await waitFor(() => expect(result.current.data?.[0]?.knowledge_base_id).toBe("newer"));

    await act(async () => {
      older.resolve({ documents: [knowledgeDocument("older")] });
    });
    expect(result.current.data?.[0]?.knowledge_base_id).toBe("newer");
    expect(result.current.loading).toBe(false);
  });

  it("keeps documents for the latest workbench knowledge base", async () => {
    const older = deferred<WorkbenchKnowledgeDocumentListResponse>();
    const newer = deferred<WorkbenchKnowledgeDocumentListResponse>();
    const getWorkbenchKnowledgeDocuments = vi
      .spyOn(adminApi, "getWorkbenchKnowledgeDocuments")
      .mockImplementation((baseId) => (baseId === "older" ? older.promise : newer.promise));
    const { result, rerender } = renderHook(({ baseId }) => useWorkbenchKnowledgeDocuments(baseId), {
      initialProps: { baseId: "older" as string | null },
    });

    await waitFor(() => expect(getWorkbenchKnowledgeDocuments).toHaveBeenCalledTimes(1));
    rerender({ baseId: "newer" });
    await waitFor(() => expect(getWorkbenchKnowledgeDocuments).toHaveBeenCalledTimes(2));

    await act(async () => {
      newer.resolve({ documents: [workbenchDocument("newer")] });
    });
    await waitFor(() => expect(result.current.data?.[0]?.knowledge_base_id).toBe("newer"));

    await act(async () => {
      older.resolve({ documents: [workbenchDocument("older")] });
    });
    expect(result.current.data?.[0]?.knowledge_base_id).toBe("newer");
    expect(result.current.loading).toBe(false);
  });

  it("does not repopulate documents after selection is cleared", async () => {
    const pending = deferred<KnowledgeDocumentListResponse>();
    const getKnowledgeDocuments = vi.spyOn(adminApi, "getKnowledgeDocuments").mockReturnValue(pending.promise);
    const { result, rerender, unmount } = renderHook(({ baseId }) => useKnowledgeDocuments(baseId), {
      initialProps: { baseId: "pending" as string | null },
    });

    await waitFor(() => expect(getKnowledgeDocuments).toHaveBeenCalledOnce());
    rerender({ baseId: null });
    await waitFor(() => expect(result.current.data).toEqual([]));

    await act(async () => {
      pending.resolve({ documents: [knowledgeDocument("pending")] });
    });
    expect(result.current.data).toEqual([]);

    unmount();
  });
});
