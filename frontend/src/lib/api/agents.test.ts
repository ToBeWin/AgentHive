import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { agentsApi, assignUsersToAgent, listAgentAssignments, listMyAgents, removeAgentUser } from "./agents";

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

describe("agentsApi", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getAgentGovernanceTargets fetches governance targets", async () => {
    const spy = stubFetchReturning(
      makeResponse({ departments: [], users: [], knowledge_bases: [], model_deployments: [] }),
    );
    await agentsApi.getAgentGovernanceTargets();
    expect(callArgs(spy)[0]).toBe("/api/v1/agents/governance-targets");
    expect(callInit(spy).method).toBe("GET");
  });

  it("getAgentInstances fetches the agent instance list", async () => {
    const spy = stubFetchReturning(makeResponse({ agents: [] }));
    await agentsApi.getAgentInstances();
    expect(callArgs(spy)[0]).toBe("/api/v1/agents/instances");
    expect(callInit(spy).method).toBe("GET");
  });

  it("getWorkbenchAgentInstances fetches the workbench agent instances", async () => {
    const spy = stubFetchReturning(makeResponse({ agents: [] }));
    await agentsApi.getWorkbenchAgentInstances();
    expect(callArgs(spy)[0]).toBe("/api/v1/agents/workbench/instances");
  });

  it("createAgentInstance posts the create payload", async () => {
    const payload = { name: "Bot", agent_key: "k1" } as const;
    const spy = stubFetchReturning(makeResponse({ id: "a1", name: "Bot" }));
    await agentsApi.createAgentInstance(payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/agents/instances");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("updateAgentInstance patches the instance with the agent id in the URL", async () => {
    const payload = { name: "Updated" } as const;
    const spy = stubFetchReturning(makeResponse({ id: "a1", name: "Updated" }));
    await agentsApi.updateAgentInstance("a1", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/agents/instances/a1");
    expect(callInit(spy).method).toBe("PATCH");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("getAgentCatalog fetches the catalog", async () => {
    const spy = stubFetchReturning(makeResponse({ agents: [] }));
    await agentsApi.getAgentCatalog();
    expect(callArgs(spy)[0]).toBe("/api/v1/agents/catalog");
  });

  it("runAgent posts the run payload with the agent key in the URL", async () => {
    const payload = { input: "hello" } as const;
    const spy = stubFetchReturning(
      makeResponse({ answer: "hi", usage: {}, model_key: "m", request_id: "r", sources: [], metadata: {} }),
    );
    await agentsApi.runAgent("bot-key", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/agents/bot-key/run");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("throws an ApiError on non-2xx responses", async () => {
    stubFetchReturning(makeResponse({ detail: "Not found" }, { status: 404 }));
    await expect(agentsApi.getAgentInstances()).rejects.toMatchObject({ status: 404, message: "Not found" });
  });
});

describe("agent assignment functions", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("listAgentAssignments fetches assignments for the agent id and unwraps the list", async () => {
    const assignments = [
      {
        id: "as1",
        agent_id: "a1",
        user_id: "u1",
        user_email: "u@x.com",
        role: "owner",
        created_at: "x",
        updated_at: "x",
        user_full_name: null,
        user_username: null,
      },
    ];
    const spy = stubFetchReturning(makeResponse({ assignments, total: 1 }));
    const result = await listAgentAssignments("a1");
    expect(callArgs(spy)[0]).toBe("/api/v1/agent-assignments/agents/a1/users");
    expect(callInit(spy).method).toBe("GET");
    expect(result).toEqual(assignments);
  });

  it("assignUsersToAgent posts the bulk assignment payload and unwraps the list", async () => {
    const users = [{ user_id: "u1", role: "member" }];
    const spy = stubFetchReturning(makeResponse({ assignments: [], total: 0 }));
    await assignUsersToAgent("a1", users);
    expect(callArgs(spy)[0]).toBe("/api/v1/agent-assignments/agents/a1/users");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify({ users }));
  });

  it("removeAgentUser deletes the specific user assignment", async () => {
    const spy = stubFetchReturning(makeResponse(null));
    await removeAgentUser("a1", "u1");
    expect(callArgs(spy)[0]).toBe("/api/v1/agent-assignments/agents/a1/users/u1");
    expect(callInit(spy).method).toBe("DELETE");
  });

  it("listMyAgents fetches my agents and unwraps the list", async () => {
    const agents = [
      {
        id: "x",
        agent_id: "a1",
        agent_name: "Bot",
        agent_key: "k",
        agent_slug: "bot",
        role: "owner",
        assigned_at: "x",
      },
    ];
    const spy = stubFetchReturning(makeResponse({ agents, total: 1 }));
    const result = await listMyAgents();
    expect(callArgs(spy)[0]).toBe("/api/v1/agent-assignments/my-agents");
    expect(callInit(spy).method).toBe("GET");
    expect(result).toEqual(agents);
  });

  it("throws an ApiError on non-2xx responses", async () => {
    stubFetchReturning(makeResponse({ detail: "Forbidden" }, { status: 403 }));
    await expect(listAgentAssignments("a1")).rejects.toMatchObject({ status: 403, message: "Forbidden" });
  });
});
