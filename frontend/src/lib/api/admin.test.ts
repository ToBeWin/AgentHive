import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { adminApi } from "./admin";
import { agentsApi } from "./agents";
import { analyticsApi } from "./analytics";
import { auditApi } from "./audit";
import { budgetsApi } from "./budgets";
import { builderApi } from "./builder";
import { channelsApi } from "./channels";
import { chatApi } from "./chat";
import { knowledgeApi } from "./knowledge";
import { agentModulesApi, licenseApi } from "./license";
import { mcpApi } from "./mcp";
import { modelsApi } from "./models";
import { orgApi } from "./org";
import { systemApi } from "./system";

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

describe("adminApi", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("composes all sub-API methods onto a single object", () => {
    expect(adminApi.getLicenseStatus).toBe(licenseApi.getLicenseStatus);
    expect(adminApi.installAgentModule).toBe(agentModulesApi.installAgentModule);
    expect(adminApi.getAgentInstances).toBe(agentsApi.getAgentInstances);
    expect(adminApi.validate).toBe(builderApi.validate);
    expect(adminApi.listServers).toBe(mcpApi.listServers);
    expect(adminApi.getModelProviders).toBe(modelsApi.getModelProviders);
    expect(adminApi.getBudgetPolicies).toBe(budgetsApi.getBudgetPolicies);
    expect(adminApi.getChannels).toBe(channelsApi.getChannels);
    expect(adminApi.getKnowledgeBases).toBe(knowledgeApi.getKnowledgeBases);
    expect(adminApi.getDepartments).toBe(orgApi.getDepartments);
    expect(adminApi.getChatSessions).toBe(chatApi.getChatSessions);
    expect(adminApi.getAnalyticsOverview).toBe(analyticsApi.getAnalyticsOverview);
    expect(adminApi.getAuditLogs).toBe(auditApi.getAuditLogs);
    expect(adminApi.getHealth).toBe(systemApi.getHealth);
  });

  it("delegates getHealth to the system API with the correct URL", async () => {
    const spy = stubFetchReturning(makeResponse({ status: "healthy", service: "agenthive" }));
    await adminApi.getHealth();
    expect(callArgs(spy)[0]).toBe("/api/v1/health");
  });
});
