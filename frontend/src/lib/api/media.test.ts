import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { mediaApi } from "./media";

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

describe("mediaApi", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getModels fetches the media model list", async () => {
    const spy = stubFetchReturning(makeResponse([]));
    await mediaApi.getModels();
    expect(callArgs(spy)[0]).toBe("/api/v1/media/models");
    expect(callInit(spy).method).toBe("GET");
  });

  it("planGeneration posts the plan request", async () => {
    const payload = { kind: "image", prompt: "a cat" } as const;
    const spy = stubFetchReturning(makeResponse({ kind: "image", prompt: "a cat" }));
    await mediaApi.planGeneration(payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/media/generations/plan");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("createGenerationJob posts the job create payload", async () => {
    const payload = { kind: "image", prompt: "a cat" } as const;
    const spy = stubFetchReturning(makeResponse({ id: "j1", kind: "image", prompt: "a cat" }));
    await mediaApi.createGenerationJob(payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/media/generations");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("getGenerationJobs fetches jobs without query string when no params", async () => {
    const spy = stubFetchReturning(makeResponse({ jobs: [], total: 0 }));
    await mediaApi.getGenerationJobs();
    expect(callArgs(spy)[0]).toBe("/api/v1/media/generations");
  });

  it("getGenerationJobs applies kind and status params to the URL", async () => {
    const spy = stubFetchReturning(makeResponse({ jobs: [], total: 0 }));
    await mediaApi.getGenerationJobs({ kind: "image", status: "succeeded", limit: 5 });
    const url = callArgs(spy)[0];
    expect(url).toContain("kind=image");
    expect(url).toContain("status=succeeded");
    expect(url).toContain("limit=5");
  });

  it("getGenerationJob fetches a job by id", async () => {
    const spy = stubFetchReturning(makeResponse({ id: "j1" }));
    await mediaApi.getGenerationJob("j1");
    expect(callArgs(spy)[0]).toBe("/api/v1/media/generations/j1");
  });

  it("getGenerationJobEvents fetches events for a job", async () => {
    const spy = stubFetchReturning(makeResponse({ job_id: "j1", events: [], total: 0 }));
    await mediaApi.getGenerationJobEvents("j1");
    expect(callArgs(spy)[0]).toBe("/api/v1/media/generations/j1/events");
  });

  it("downloadGenerationOutput downloads a blob with the job id and output index", async () => {
    const spy = vi.fn<FetchLike>(() =>
      Promise.resolve(
        new Response(new Blob(["img"], { type: "image/png" }), {
          status: 200,
          headers: { "content-disposition": 'attachment; filename="out.png"' },
        }),
      ),
    );
    vi.stubGlobal("fetch", spy);
    const result = await mediaApi.downloadGenerationOutput("j1", 0);
    expect(callArgs(spy)[0]).toBe("/api/v1/media/generations/j1/outputs/0/download");
    expect(callInit(spy).method).toBe("GET");
    expect(result.filename).toBe("out.png");
  });

  it("enqueueGenerationJob posts to the enqueue endpoint", async () => {
    const spy = stubFetchReturning(makeResponse({ job_id: "j1", task_id: "t1", queued: true }));
    await mediaApi.enqueueGenerationJob("j1");
    expect(callArgs(spy)[0]).toBe("/api/v1/media/generations/j1/enqueue");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify({}));
  });

  it("runGenerationJob posts to the run endpoint", async () => {
    const spy = stubFetchReturning(makeResponse({ id: "j1" }));
    await mediaApi.runGenerationJob("j1");
    expect(callArgs(spy)[0]).toBe("/api/v1/media/generations/j1/run");
    expect(callInit(spy).method).toBe("POST");
  });

  it("pollGenerationJob posts to the poll endpoint", async () => {
    const spy = stubFetchReturning(makeResponse({ id: "j1" }));
    await mediaApi.pollGenerationJob("j1");
    expect(callArgs(spy)[0]).toBe("/api/v1/media/generations/j1/poll");
    expect(callInit(spy).method).toBe("POST");
  });

  it("enqueueRunningGenerationPolls posts with the limit in the URL", async () => {
    const spy = stubFetchReturning(makeResponse({ requested: 0, queued: 0, skipped: 0, failed: 0, items: [] }));
    await mediaApi.enqueueRunningGenerationPolls(30);
    expect(callArgs(spy)[0]).toBe("/api/v1/media/generations/poll/enqueue?limit=30");
    expect(callInit(spy).method).toBe("POST");
  });

  it("enqueueGenerationPoll posts to the poll enqueue endpoint", async () => {
    const spy = stubFetchReturning(makeResponse({ job_id: "j1", task_id: "t1", queued: true }));
    await mediaApi.enqueueGenerationPoll("j1");
    expect(callArgs(spy)[0]).toBe("/api/v1/media/generations/j1/poll/enqueue");
    expect(callInit(spy).method).toBe("POST");
  });

  it("retryGenerationJob posts to the retry endpoint", async () => {
    const spy = stubFetchReturning(makeResponse({ id: "j1" }));
    await mediaApi.retryGenerationJob("j1");
    expect(callArgs(spy)[0]).toBe("/api/v1/media/generations/j1/retry");
    expect(callInit(spy).method).toBe("POST");
  });

  it("cancelGenerationJob posts to the cancel endpoint", async () => {
    const spy = stubFetchReturning(makeResponse({ id: "j1" }));
    await mediaApi.cancelGenerationJob("j1");
    expect(callArgs(spy)[0]).toBe("/api/v1/media/generations/j1/cancel");
    expect(callInit(spy).method).toBe("POST");
  });

  it("updateGenerationJobStatus patches the status with the job id in the URL", async () => {
    const payload = { status: "succeeded" } as const;
    const spy = stubFetchReturning(makeResponse({ id: "j1" }));
    await mediaApi.updateGenerationJobStatus("j1", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/media/generations/j1/status");
    expect(callInit(spy).method).toBe("PATCH");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("throws an ApiError on non-2xx responses", async () => {
    stubFetchReturning(makeResponse({ detail: "Not found" }, { status: 404 }));
    await expect(mediaApi.getModels()).rejects.toMatchObject({ status: 404, message: "Not found" });
  });
});
