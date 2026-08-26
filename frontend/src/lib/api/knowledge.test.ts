import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { knowledgeApi } from "./knowledge";

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

describe("knowledgeApi", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getKnowledgeGovernanceTargets fetches governance targets", async () => {
    const spy = stubFetchReturning(makeResponse({ departments: [] }));
    await knowledgeApi.getKnowledgeGovernanceTargets();
    expect(callArgs(spy)[0]).toBe("/api/v1/knowledge/governance-targets");
    expect(callInit(spy).method).toBe("GET");
  });

  it("getKnowledgeBases fetches the knowledge base list", async () => {
    const spy = stubFetchReturning(makeResponse({ bases: [] }));
    await knowledgeApi.getKnowledgeBases();
    expect(callArgs(spy)[0]).toBe("/api/v1/knowledge/bases");
  });

  it("getWorkbenchKnowledgeBases fetches the workbench bases", async () => {
    const spy = stubFetchReturning(makeResponse({ bases: [] }));
    await knowledgeApi.getWorkbenchKnowledgeBases();
    expect(callArgs(spy)[0]).toBe("/api/v1/knowledge/workbench/bases");
  });

  it("createKnowledgeBase posts the create payload", async () => {
    const payload = { name: "KB1", visibility: "tenant", rag_engine: "pgvector" } as const;
    const spy = stubFetchReturning(makeResponse({ id: "kb1", name: "KB1" }));
    await knowledgeApi.createKnowledgeBase(payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/knowledge/bases");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("deleteKnowledgeBase deletes the base by id", async () => {
    const spy = stubFetchReturning(makeResponse({ id: "kb1", deleted: true }));
    await knowledgeApi.deleteKnowledgeBase("kb1");
    expect(callArgs(spy)[0]).toBe("/api/v1/knowledge/bases/kb1");
    expect(callInit(spy).method).toBe("DELETE");
  });

  it("getKnowledgeDocuments fetches documents for the base id", async () => {
    const spy = stubFetchReturning(makeResponse({ documents: [] }));
    await knowledgeApi.getKnowledgeDocuments("kb1");
    expect(callArgs(spy)[0]).toBe("/api/v1/knowledge/bases/kb1/documents");
  });

  it("getWorkbenchKnowledgeDocuments fetches workbench documents for the base id", async () => {
    const spy = stubFetchReturning(makeResponse({ documents: [] }));
    await knowledgeApi.getWorkbenchKnowledgeDocuments("kb1");
    expect(callArgs(spy)[0]).toBe("/api/v1/knowledge/workbench/bases/kb1/documents");
  });

  it("deleteKnowledgeDocument deletes the document by base and document id", async () => {
    const spy = stubFetchReturning(makeResponse({ id: "d1", deleted: true }));
    await knowledgeApi.deleteKnowledgeDocument("kb1", "d1");
    expect(callArgs(spy)[0]).toBe("/api/v1/knowledge/bases/kb1/documents/d1");
    expect(callInit(spy).method).toBe("DELETE");
  });

  it("reingestKnowledgeDocument posts to the reingest endpoint", async () => {
    const spy = stubFetchReturning(
      makeResponse({ document: {}, auto_ingest: true, ingest_status: null, message: "ok", diagnostics: {} }),
    );
    await knowledgeApi.reingestKnowledgeDocument("kb1", "d1");
    expect(callArgs(spy)[0]).toBe("/api/v1/knowledge/bases/kb1/documents/d1/reingest");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify({}));
  });

  it("uploadKnowledgeDocument posts FormData to the upload endpoint", async () => {
    const spy = stubFetchReturning(
      makeResponse({ document: {}, auto_ingest: true, ingest_status: null, message: "ok", diagnostics: {} }),
    );
    const file = new File(["content"], "doc.txt", { type: "text/plain" });
    await knowledgeApi.uploadKnowledgeDocument("kb1", file);
    expect(callArgs(spy)[0]).toBe("/api/v1/knowledge/bases/kb1/documents/upload");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBeInstanceOf(FormData);
    expect((callInit(spy).headers as Headers).get("content-type")).toBeNull();
  });

  it("completeKnowledgeDocumentUpload posts the complete payload", async () => {
    const payload = { auto_ingest: true } as const;
    const spy = stubFetchReturning(
      makeResponse({ document: {}, auto_ingest: true, ingest_status: null, message: "ok", diagnostics: {} }),
    );
    await knowledgeApi.completeKnowledgeDocumentUpload("kb1", "d1", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/knowledge/bases/kb1/documents/d1/complete-upload");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("runRetrievalTest posts the retrieval test payload", async () => {
    const payload = { query: "q", top_k: 5 } as const;
    const spy = stubFetchReturning(
      makeResponse({
        knowledge_base_id: "kb1",
        query: "q",
        engine: "pgvector",
        elapsed_ms: 10,
        results: [],
        diagnostics: {},
        checked_at: "x",
      }),
    );
    await knowledgeApi.runRetrievalTest("kb1", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/knowledge/bases/kb1/retrieval-test");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("throws an ApiError on non-2xx responses", async () => {
    stubFetchReturning(makeResponse({ detail: "Not found" }, { status: 404 }));
    await expect(knowledgeApi.getKnowledgeBases()).rejects.toMatchObject({ status: 404, message: "Not found" });
  });
});
