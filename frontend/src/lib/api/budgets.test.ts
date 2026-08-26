import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { budgetsApi } from "./budgets";

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

describe("budgetsApi", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getBudgetSummary fetches summary without query string when no filters", async () => {
    const spy = stubFetchReturning(makeResponse({ tenant_id: "t1", currency: "USD", period: "monthly" }));
    await budgetsApi.getBudgetSummary();
    expect(callArgs(spy)[0]).toBe("/api/v1/budgets/summary");
  });

  it("getBudgetSummary applies period filters to the query string", async () => {
    const spy = stubFetchReturning(makeResponse({ tenant_id: "t1", currency: "USD", period: "daily" }));
    await budgetsApi.getBudgetSummary({ period: "daily", period_start: "2026-01-01" });
    const url = callArgs(spy)[0];
    expect(url).toContain("period=daily");
    expect(url).toContain("period_start=2026-01-01");
  });

  it("getBudgetPolicies fetches the policy list", async () => {
    const spy = stubFetchReturning(makeResponse({ policies: [] }));
    await budgetsApi.getBudgetPolicies();
    expect(callArgs(spy)[0]).toBe("/api/v1/budgets/policies");
  });

  it("getBudgetGovernanceTargets fetches governance targets", async () => {
    const spy = stubFetchReturning(
      makeResponse({ departments: [], cost_centers: [], users: [], agents: [], channels: [] }),
    );
    await budgetsApi.getBudgetGovernanceTargets();
    expect(callArgs(spy)[0]).toBe("/api/v1/budgets/governance-targets");
  });

  it("getBudgetLedger fetches the budget ledger with limit=12", async () => {
    const spy = stubFetchReturning(makeResponse({ items: [], total: 0, limit: 12, offset: 0 }));
    await budgetsApi.getBudgetLedger();
    expect(callArgs(spy)[0]).toBe("/api/v1/budgets/budget-ledger?limit=12");
  });

  it("getBudgetUsageLedger fetches the usage ledger with limit=12", async () => {
    const spy = stubFetchReturning(makeResponse({ items: [], total: 0, limit: 12, offset: 0 }));
    await budgetsApi.getBudgetUsageLedger();
    expect(callArgs(spy)[0]).toBe("/api/v1/budgets/usage-ledger?limit=12");
  });

  it("getBudgetUsageBreakdown fetches breakdown with the dimension in the URL", async () => {
    const spy = stubFetchReturning(
      makeResponse({
        tenant_id: "t1",
        dimension: "user",
        items: [],
        total_request_count: 0,
        total_cost_amount: "0",
        total_tokens: 0,
      }),
    );
    await budgetsApi.getBudgetUsageBreakdown("user");
    expect(callArgs(spy)[0]).toBe("/api/v1/budgets/usage-breakdown?dimension=user&limit=8");
  });

  it("getBudgetUsageBreakdown defaults to the department dimension", async () => {
    const spy = stubFetchReturning(
      makeResponse({
        tenant_id: "t1",
        dimension: "department",
        items: [],
        total_request_count: 0,
        total_cost_amount: "0",
        total_tokens: 0,
      }),
    );
    await budgetsApi.getBudgetUsageBreakdown();
    expect(callArgs(spy)[0]).toBe("/api/v1/budgets/usage-breakdown?dimension=department&limit=8");
  });

  it("exportBudgetLedgerCsv downloads the CSV export with default limit", async () => {
    const spy = stubFetchReturning(makeResponse("a,b,c\n1,2,3", { headers: { "content-type": "text/csv" } }));
    await budgetsApi.exportBudgetLedgerCsv();
    const url = callArgs(spy)[0];
    expect(url).toContain("/api/v1/budgets/budget-ledger/export?");
    expect(url).toContain("limit=5000");
    expect(callInit(spy).method).toBe("GET");
  });

  it("exportBudgetLedgerJson downloads the JSON export with format=json", async () => {
    const spy = stubFetchReturning(makeResponse('{"items":[]}'));
    await budgetsApi.exportBudgetLedgerJson();
    const url = callArgs(spy)[0];
    expect(url).toContain("format=json");
  });

  it("exportUsageLedgerCsv downloads the usage CSV export", async () => {
    const spy = stubFetchReturning(makeResponse("a,b\n1,2", { headers: { "content-type": "text/csv" } }));
    await budgetsApi.exportUsageLedgerCsv();
    const url = callArgs(spy)[0];
    expect(url).toContain("/api/v1/budgets/usage-ledger/export?");
  });

  it("exportUsageLedgerJson downloads the usage JSON export", async () => {
    const spy = stubFetchReturning(makeResponse('{"items":[]}'));
    await budgetsApi.exportUsageLedgerJson();
    const url = callArgs(spy)[0];
    expect(url).toContain("format=json");
  });

  it("saveBudgetPolicy posts the policy payload", async () => {
    const payload = {
      scope_type: "tenant",
      period: "monthly",
      budget_type: "hard",
      currency: "USD",
      amount_limit: "100",
      alert_threshold_pct: 80,
      status: "active",
    } as const;
    const spy = stubFetchReturning(makeResponse({ id: "p1" }));
    await budgetsApi.saveBudgetPolicy(payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/budgets/policies");
    expect(callInit(spy).method).toBe("POST");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("updateBudgetPolicyStatus patches the status with the policy id in the URL", async () => {
    const payload = { status: "inactive" } as const;
    const spy = stubFetchReturning(makeResponse({ id: "p1" }));
    await budgetsApi.updateBudgetPolicyStatus("p1", payload);
    expect(callArgs(spy)[0]).toBe("/api/v1/budgets/policies/p1/status");
    expect(callInit(spy).method).toBe("PATCH");
    expect(callInit(spy).body).toBe(JSON.stringify(payload));
  });

  it("throws an ApiError on non-2xx responses", async () => {
    stubFetchReturning(makeResponse({ detail: "Forbidden" }, { status: 403 }));
    await expect(budgetsApi.getBudgetPolicies()).rejects.toMatchObject({ status: 403, message: "Forbidden" });
  });
});
