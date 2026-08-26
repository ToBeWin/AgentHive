import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { LLMPolicyUpsertRequest } from "./models";
import { modelsApi } from "./models";

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

describe("modelsApi", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getModelProviders fetches providers", async () => {
    const spy = stubFetchReturning(makeResponse({ providers: [] }));
    await modelsApi.getModelProviders();
    expect(callArgs(spy)[0]).toBe("/api/v1/models/providers");
    expect(callInit(spy).method).toBe("GET");
  });

  it("getModelDeployments fetches deployments", async () => {
    const spy = stubFetchReturning(makeResponse({ deployments: [] }));
    await modelsApi.getModelDeployments();
    expect(callArgs(spy)[0]).toBe("/api/v1/models/deployments");
  });

  it("getModelReadiness fetches readiness", async () => {
    const spy = stubFetchReturning(makeResponse({ generated_at: "x", summary: {}, deployments: [] }));
    await modelsApi.getModelReadiness();
    expect(callArgs(spy)[0]).toBe("/api/v1/models/readiness");
  });

  it("getModelPolicies fetches policies", async () => {
    const spy = stubFetchReturning(makeResponse({ policies: [] }));
    await modelsApi.getModelPolicies();
    expect(callArgs(spy)[0]).toBe("/api/v1/models/policies");
  });

  it("getModelPrices fetches prices", async () => {
    const spy = stubFetchReturning(makeResponse({ prices: [] }));
    await modelsApi.getModelPrices();
    expect(callArgs(spy)[0]).toBe("/api/v1/models/prices");
  });

  it("getModelConnectionTests fetches connection tests with the limit in the URL", async () => {
    const spy = stubFetchReturning(makeResponse({ tests: [] }));
    await modelsApi.getModelConnectionTests(5);
    expect(callArgs(spy)[0]).toBe("/api/v1/models/connection-tests?limit=5");
  });

  it("getModelConnectionTests defaults to limit=20", async () => {
    const spy = stubFetchReturning(makeResponse({ tests: [] }));
    await modelsApi.getModelConnectionTests();
    expect(callArgs(spy)[0]).toBe("/api/v1/models/connection-tests?limit=20");
  });

  it("getModelGovernanceTargets fetches governance targets", async () => {
    const spy = stubFetchReturning(
      makeResponse({ departments: [], cost_centers: [], users: [], agents: [], channels: [] }),
    );
    await modelsApi.getModelGovernanceTargets();
    expect(callArgs(spy)[0]).toBe("/api/v1/models/governance-targets");
  });

  it("saveModelPrice puts the price payload", async () => {
    const payload = {
      provider_key: "p1",
      model_key: "m1",
      input_per_1k_tokens: "0.01",
      output_per_1k_tokens: "0.02",
    } as const;
    const spy = stubFetchReturning(makeResponse({ id: "pr1" }));
    await modelsApi.saveModelPrice(payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/models/prices");
    expect(callInit(spy).method).toBe("PUT");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("saveModelPolicy posts the policy payload", async () => {
    const payload: LLMPolicyUpsertRequest = {
      name: "P1",
      scope_type: "tenant",
      effect: "allow",
      allowed_models: [],
      allowed_routing_keys: [],
      priority: 1,
      status: "active",
    };
    const spy = stubFetchReturning(makeResponse({ id: "po1" }));
    await modelsApi.saveModelPolicy(payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/models/policies");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("updateModelPolicyStatus patches the status with the policy id in the URL", async () => {
    const payload = { status: "inactive" } as const;
    const spy = stubFetchReturning(makeResponse({ id: "po1" }));
    await modelsApi.updateModelPolicyStatus("po1", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/models/policies/po1/status");
    expect(callInit(spy).method).toBe("PATCH");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("saveModelCredential puts the credential with the provider key in the URL", async () => {
    const payload = { display_name: "D1", api_key: "k" } as const;
    const spy = stubFetchReturning(makeResponse({ provider_key: "p1" }));
    await modelsApi.saveModelCredential("p1", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/models/providers/p1/credential");
    expect(callInit(spy).method).toBe("PUT");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("testModelConnection posts the test request", async () => {
    const payload = { provider_key: "p1" } as const;
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await modelsApi.testModelConnection(payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/models/test-connection");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("runDeploymentAcceptanceTest posts to the acceptance-test endpoint with the deployment id", async () => {
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await modelsApi.runDeploymentAcceptanceTest("d1");
    expect(callArgs(spy)[0]).toBe("/api/v1/models/deployments/d1/acceptance-test");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify({}));
  });

  it("runDeploymentAcceptanceTest posts a custom payload when provided", async () => {
    const payload = { prompt: "hi", max_tokens: 10 } as const;
    const spy = stubFetchReturning(makeResponse({ ok: true }));
    await modelsApi.runDeploymentAcceptanceTest("d1", payload);
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("throws an ApiError on non-2xx responses", async () => {
    stubFetchReturning(makeResponse({ detail: "Forbidden" }, { status: 403 }));
    await expect(modelsApi.getModelProviders()).rejects.toMatchObject({ status: 403, message: "Forbidden" });
  });
});
