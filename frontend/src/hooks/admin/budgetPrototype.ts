import type {
  AnalyticsOverviewResponse,
  BudgetLedgerItem,
  BudgetLedgerResponse,
  BudgetPeriod,
  BudgetPolicyResponse,
  BudgetPolicyStatus,
  BudgetPolicyUpsertRequest,
  BudgetSummaryResponse,
  UsageBreakdownDimension,
  UsageBreakdownItem,
  UsageBreakdownResponse,
  UsageLedgerItem,
  UsageLedgerResponse,
} from "../../lib/api";

const PROTOTYPE_NOW = "2026-01-01T09:12:00.000Z";
const PROTOTYPE_MONTH_START = "2026-01-01T00:00:00.000Z";
const PROTOTYPE_MONTH_END = "2026-01-31T23:59:59.000Z";
const PROTOTYPE_DAY_START = "2026-01-01T00:00:00.000Z";
const PROTOTYPE_DAY_END = "2026-01-01T23:59:59.000Z";

const TENANT_ID = "00000000-0000-4000-8000-000000000001";
const USER_ID = "00000000-0000-4000-8000-000000000202";
const DEPARTMENT_ID = "00000000-0000-4000-8000-000000000301";
const COST_CENTER_ID = "00000000-0000-4000-8000-000000000401";
const AGENT_ID = "00000000-0000-4000-8000-000000000701";
const CHANNEL_ID = "00000000-0000-4000-8000-000000000801";
const CONVERSATION_ID = "00000000-0000-4000-8000-000000000901";
const PRIMARY_REQUEST_ID = "proto-run-001";
const PREMIUM_DENIED_REQUEST_ID = "proto-run-002";
const FALLBACK_REQUEST_ID = "proto-run-003";

export const PROTOTYPE_BUDGET_POLICIES: BudgetPolicyResponse[] = [
  {
    alert_threshold_pct: 80,
    amount_limit: "1000.0000",
    amount_spent: "186.4200",
    budget_type: "hard",
    created_at: PROTOTYPE_MONTH_START,
    currency: "USD",
    custom_period_end: null,
    custom_period_start: null,
    description: "Tenant-wide hard stop before any model call leaves AgentHive LLM Gateway.",
    health: "ok",
    id: "00000000-0000-4000-8000-000000140001",
    name: "Tenant monthly hard cap",
    period: "monthly",
    scope_id: null,
    scope_type: "tenant",
    status: "active",
    tenant_id: TENANT_ID,
    token_limit: 1000000,
    tokens_used: 248360,
    updated_at: PROTOTYPE_NOW,
  },
  {
    alert_threshold_pct: 75,
    amount_limit: "850.0000",
    amount_spent: "716.2800",
    budget_type: "soft",
    created_at: PROTOTYPE_MONTH_START,
    currency: "USD",
    custom_period_end: null,
    custom_period_start: null,
    description: "Customer Success receives warnings before premium routes are denied.",
    health: "warning",
    id: "00000000-0000-4000-8000-000000140002",
    name: "Customer Success model spend",
    period: "monthly",
    scope_id: DEPARTMENT_ID,
    scope_type: "department",
    status: "active",
    tenant_id: TENANT_ID,
    token_limit: 320000,
    tokens_used: 268100,
    updated_at: PROTOTYPE_NOW,
  },
  {
    alert_threshold_pct: 85,
    amount_limit: "125.0000",
    amount_spent: "116.0600",
    budget_type: "hard",
    created_at: PROTOTYPE_MONTH_START,
    currency: "USD",
    custom_period_end: null,
    custom_period_start: null,
    description: "Customer Service Agent must fall back to cost-chat when premium route is near cap.",
    health: "warning",
    id: "00000000-0000-4000-8000-000000140003",
    name: "Customer Service Agent route guard",
    period: "monthly",
    scope_id: AGENT_ID,
    scope_type: "agent",
    status: "active",
    tenant_id: TENANT_ID,
    token_limit: 90000,
    tokens_used: 84160,
    updated_at: PROTOTYPE_NOW,
  },
];

export const PROTOTYPE_USAGE_LEDGER: UsageLedgerItem[] = [
  {
    agent_id: AGENT_ID,
    channel_id: CHANNEL_ID,
    conversation_id: CONVERSATION_ID,
    cost_amount: "0.0064",
    cost_center_id: COST_CENTER_ID,
    created_at: "2026-01-01T09:11:30.000Z",
    currency: "USD",
    department_id: DEPARTMENT_ID,
    deployment_id: "00000000-0000-4000-8000-000000100004",
    error_code: null,
    id: "00000000-0000-4000-8000-000000150001",
    input_tokens: 1280,
    metadata: {
      budget_guard: "settled",
      fallback_attempts: 0,
      provider_key: "qwen",
      route_reason: "department policy selected cn-primary-chat",
    },
    model_key: "qwen-plus",
    output_tokens: 426,
    request_id: PRIMARY_REQUEST_ID,
    status: "success",
    tenant_id: TENANT_ID,
    total_tokens: 1706,
    user_id: USER_ID,
  },
  {
    agent_id: AGENT_ID,
    channel_id: CHANNEL_ID,
    conversation_id: CONVERSATION_ID,
    cost_amount: "0.0000",
    cost_center_id: COST_CENTER_ID,
    created_at: "2026-01-01T09:09:20.000Z",
    currency: "USD",
    department_id: DEPARTMENT_ID,
    deployment_id: "00000000-0000-4000-8000-000000100001",
    error_code: "budget_hard_limit",
    id: "00000000-0000-4000-8000-000000150002",
    input_tokens: 2100,
    metadata: {
      budget_guard: "denied",
      fallback_attempts: 0,
      provider_key: "openai",
      route_reason: "premium-chat denied by agent hard cap",
    },
    model_key: "gpt-4o",
    output_tokens: 0,
    request_id: PREMIUM_DENIED_REQUEST_ID,
    status: "denied",
    tenant_id: TENANT_ID,
    total_tokens: 2100,
    user_id: USER_ID,
  },
  {
    agent_id: AGENT_ID,
    channel_id: CHANNEL_ID,
    conversation_id: CONVERSATION_ID,
    cost_amount: "0.0031",
    cost_center_id: COST_CENTER_ID,
    created_at: "2026-01-01T09:09:28.000Z",
    currency: "USD",
    department_id: DEPARTMENT_ID,
    deployment_id: "00000000-0000-4000-8000-000000100005",
    error_code: null,
    id: "00000000-0000-4000-8000-000000150003",
    input_tokens: 2100,
    metadata: {
      budget_guard: "settled",
      fallback_attempts: 1,
      fallback_from: "premium-chat",
      provider_key: "deepseek",
      route_reason: "fallback selected cost-chat after premium denial",
    },
    model_key: "deepseek-v4-flash",
    output_tokens: 612,
    request_id: FALLBACK_REQUEST_ID,
    status: "success",
    tenant_id: TENANT_ID,
    total_tokens: 2712,
    user_id: USER_ID,
  },
];

export const PROTOTYPE_BUDGET_LEDGER: BudgetLedgerItem[] = [
  budgetLedgerItem({
    actualCost: "0.0064",
    actualTokens: 1706,
    budgetId: "00000000-0000-4000-8000-000000140002",
    createdAt: "2026-01-01T09:11:31.000Z",
    estimatedCost: "0.0070",
    estimatedTokens: 1900,
    eventType: "settle",
    id: "00000000-0000-4000-8000-000000160001",
    reason: "Qwen call settled to Customer Success department ledger.",
    requestId: PRIMARY_REQUEST_ID,
    reservationId: "reserve-proto-run-001",
    scopeId: DEPARTMENT_ID,
    scopeType: "department",
  }),
  budgetLedgerItem({
    actualCost: "0.0000",
    actualTokens: 0,
    budgetId: "00000000-0000-4000-8000-000000140003",
    createdAt: "2026-01-01T09:09:20.000Z",
    estimatedCost: "0.0410",
    estimatedTokens: 4200,
    eventType: "deny",
    id: "00000000-0000-4000-8000-000000160002",
    reason: "Premium route denied before model call because Agent hard cap is above threshold.",
    requestId: PREMIUM_DENIED_REQUEST_ID,
    reservationId: "reserve-proto-run-002",
    scopeId: AGENT_ID,
    scopeType: "agent",
  }),
  budgetLedgerItem({
    actualCost: "0.0031",
    actualTokens: 2712,
    budgetId: "00000000-0000-4000-8000-000000140003",
    createdAt: "2026-01-01T09:09:29.000Z",
    estimatedCost: "0.0042",
    estimatedTokens: 3000,
    eventType: "settle",
    id: "00000000-0000-4000-8000-000000160003",
    reason: "DeepSeek fallback settled after premium route denial.",
    requestId: FALLBACK_REQUEST_ID,
    reservationId: "reserve-proto-run-003",
    scopeId: AGENT_ID,
    scopeType: "agent",
  }),
  budgetLedgerItem({
    actualCost: "0.0000",
    actualTokens: 0,
    budgetId: "00000000-0000-4000-8000-000000140002",
    createdAt: "2026-01-01T09:08:50.000Z",
    estimatedCost: "0.0000",
    estimatedTokens: 0,
    eventType: "alert",
    id: "00000000-0000-4000-8000-000000160004",
    reason: "Customer Success exceeded 75% soft threshold.",
    requestId: "proto-alert-001",
    reservationId: "alert-customer-success",
    scopeId: DEPARTMENT_ID,
    scopeType: "department",
  }),
];

export function prototypeBudgetSummary(period: BudgetPeriod): BudgetSummaryResponse {
  const scale = period === "daily" ? 0.08 : 1;
  const amountSpent = (1018.76 * scale).toFixed(4);
  const tokenUsed = Math.round(354520 * scale);
  return {
    active_policy_count: 3,
    by_scope: [
      {
        active_policy_count: 1,
        amount_limit: "1000.0000",
        amount_spent: (186.42 * scale).toFixed(4),
        policy_count: 1,
        scope_type: "tenant",
        token_limit: 1000000,
        tokens_used: Math.round(248360 * scale),
      },
      {
        active_policy_count: 1,
        amount_limit: "850.0000",
        amount_spent: (716.28 * scale).toFixed(4),
        policy_count: 1,
        scope_type: "department",
        token_limit: 320000,
        tokens_used: Math.round(268100 * scale),
      },
      {
        active_policy_count: 1,
        amount_limit: "125.0000",
        amount_spent: (116.06 * scale).toFixed(4),
        policy_count: 1,
        scope_type: "agent",
        token_limit: 90000,
        tokens_used: Math.round(84160 * scale),
      },
    ],
    currency: "USD",
    exceeded_policy_count: 0,
    generated_at: PROTOTYPE_NOW,
    hard_policy_count: 2,
    metadata: {
      demo_request_id: PRIMARY_REQUEST_ID,
      fallback_request_id: FALLBACK_REQUEST_ID,
      governance_flow: "pre_call_reserve -> budget_guard -> model_route -> usage_settle -> ledger",
      source: "prototype_governance_ledger",
    },
    period,
    period_end: period === "daily" ? PROTOTYPE_DAY_END : PROTOTYPE_MONTH_END,
    period_start: period === "daily" ? PROTOTYPE_DAY_START : PROTOTYPE_MONTH_START,
    policy_count: 3,
    soft_policy_count: 1,
    tenant_id: TENANT_ID,
    total_amount_limit: "1975.0000",
    total_amount_spent: amountSpent,
    total_token_limit: 1410000,
    total_tokens_used: tokenUsed,
    warning_policy_count: 2,
  };
}

export function prototypeAnalyticsOverview(): AnalyticsOverviewResponse {
  return {
    agent_usage: [
      {
        agent_id: AGENT_ID,
        agent_key: "customer_service",
        agent_name: "E-commerce Customer Service Agent",
        cost_usd: 716.28,
        requests: 1840,
        tokens: 268100,
      },
      {
        agent_id: "00000000-0000-4000-8000-000000000702",
        agent_key: "copywriting",
        agent_name: "Copywriting Assistant",
        cost_usd: 186.42,
        requests: 870,
        tokens: 52480,
      },
    ],
    daily_usage: [
      { cost_usd: 112.4, date: "2026-01-01", requests: 420, tokens: 38200 },
      { cost_usd: 148.7, date: "2026-01-02", requests: 530, tokens: 49600 },
      { cost_usd: 132.9, date: "2026-01-03", requests: 490, tokens: 45240 },
      { cost_usd: 176.2, date: "2026-01-04", requests: 680, tokens: 61200 },
      { cost_usd: 205.1, date: "2026-01-05", requests: 760, tokens: 73460 },
      { cost_usd: 243.46, date: "2026-01-06", requests: 843, tokens: 86820 },
    ],
    department_usage: [
      {
        cost_usd: 716.28,
        department_id: DEPARTMENT_ID,
        department_name: "Customer Success",
        requests: 1840,
        tokens: 268100,
      },
      {
        cost_usd: 302.48,
        department_id: "00000000-0000-4000-8000-000000000302",
        department_name: "Marketing",
        requests: 1383,
        tokens: 86420,
      },
    ],
    generated_at: PROTOTYPE_NOW,
    metadata: {
      budget_guard: "pre-call enforced",
      demo_request_id: PRIMARY_REQUEST_ID,
      fallback_request_id: FALLBACK_REQUEST_ID,
      license: "enterprise-active",
      storage: "postgres-pgvector-minio",
    },
    model_usage: [
      {
        cost_usd: 616.28,
        model_key: "qwen-plus",
        requests: 1560,
        tokens: 224300,
      },
      {
        cost_usd: 116.06,
        model_key: "deepseek-v4-flash",
        requests: 620,
        tokens: 84160,
      },
      {
        cost_usd: 286.42,
        model_key: "moonshot-v1-128k",
        requests: 1043,
        tokens: 46200,
      },
      {
        cost_usd: 0,
        model_key: "gpt-4o",
        requests: 18,
        tokens: 12860,
      },
    ],
    totals: {
      success_rate: 0.982,
      total_cost_usd: 1018.76,
      total_requests: 3223,
      total_tokens: 354520,
    },
    user_usage: [
      {
        cost_usd: 716.28,
        requests: 1840,
        tokens: 268100,
        user_id: USER_ID,
        user_name: "Operations Lead",
      },
      {
        cost_usd: 186.42,
        requests: 870,
        tokens: 52480,
        user_id: "00000000-0000-4000-8000-000000000203",
        user_name: "Content Manager",
      },
    ],
  };
}

export function prototypeUsageLedger(): UsageLedgerResponse {
  return {
    items: PROTOTYPE_USAGE_LEDGER,
    limit: 12,
    offset: 0,
    total: PROTOTYPE_USAGE_LEDGER.length,
  };
}

export function prototypeBudgetLedger(): BudgetLedgerResponse {
  return {
    items: PROTOTYPE_BUDGET_LEDGER,
    limit: 12,
    offset: 0,
    total: PROTOTYPE_BUDGET_LEDGER.length,
  };
}

export function prototypeUsageBreakdown(dimension: UsageBreakdownDimension): UsageBreakdownResponse {
  const items = breakdownItems(dimension);
  return {
    dimension,
    items,
    period_end: PROTOTYPE_MONTH_END,
    period_start: PROTOTYPE_MONTH_START,
    tenant_id: TENANT_ID,
    total_cost_amount: sumCurrency(items),
    total_request_count: items.reduce((total, item) => total + item.request_count, 0),
    total_tokens: items.reduce((total, item) => total + item.total_tokens, 0),
  };
}

export function createPrototypeBudgetPolicy(payload: BudgetPolicyUpsertRequest): BudgetPolicyResponse {
  return {
    alert_threshold_pct: payload.alert_threshold_pct,
    amount_limit: String(payload.amount_limit),
    amount_spent: "0.0000",
    budget_type: payload.budget_type,
    created_at: PROTOTYPE_NOW,
    currency: payload.currency,
    custom_period_end: payload.custom_period_end ?? null,
    custom_period_start: payload.custom_period_start ?? null,
    description: payload.description ?? null,
    health: "ok",
    id: payload.id ?? "00000000-0000-4000-8000-000000149999",
    name: payload.name ?? null,
    period: payload.period,
    scope_id: payload.scope_id ?? null,
    scope_type: payload.scope_type,
    status: payload.status,
    tenant_id: TENANT_ID,
    token_limit: payload.token_limit ?? null,
    tokens_used: 0,
    updated_at: new Date().toISOString(),
  };
}

export function updatePrototypeBudgetPolicyStatus(policyId: string, status: BudgetPolicyStatus): BudgetPolicyResponse {
  const existing = PROTOTYPE_BUDGET_POLICIES.find((policy) => policy.id === policyId) ?? PROTOTYPE_BUDGET_POLICIES[0];
  return { ...existing, status, updated_at: new Date().toISOString() };
}

export function prototypeBudgetExport(format: "csv" | "json", ledger: "budget" | "usage") {
  const rows = ledger === "budget" ? PROTOTYPE_BUDGET_LEDGER : PROTOTYPE_USAGE_LEDGER;
  if (format === "json") {
    return JSON.stringify(rows, null, 2);
  }
  const keys = Object.keys(rows[0] ?? {});
  return [
    keys.join(","),
    ...rows.map((row) => keys.map((key) => JSON.stringify(row[key as keyof typeof row] ?? "")).join(",")),
  ].join("\n");
}

function budgetLedgerItem({
  actualCost,
  actualTokens,
  budgetId,
  createdAt,
  estimatedCost,
  estimatedTokens,
  eventType,
  id,
  reason,
  requestId,
  reservationId,
  scopeId,
  scopeType,
}: {
  actualCost: string;
  actualTokens: number;
  budgetId: string;
  createdAt: string;
  estimatedCost: string;
  estimatedTokens: number;
  eventType: BudgetLedgerItem["event_type"];
  id: string;
  reason: string;
  requestId: string;
  reservationId: string;
  scopeId: string;
  scopeType: BudgetLedgerItem["scope_type"];
}): BudgetLedgerItem {
  return {
    actual_cost_amount: actualCost,
    actual_tokens: actualTokens,
    agent_id: AGENT_ID,
    budget_id: budgetId,
    channel_id: CHANNEL_ID,
    conversation_id: CONVERSATION_ID,
    cost_center_id: COST_CENTER_ID,
    created_at: createdAt,
    currency: "USD",
    department_id: DEPARTMENT_ID,
    estimated_cost_amount: estimatedCost,
    estimated_tokens: estimatedTokens,
    event_type: eventType,
    id,
    metadata: { source: "prototype_governance_ledger" },
    reason,
    request_id: requestId,
    reservation_id: reservationId,
    scope_id: scopeId,
    scope_type: scopeType,
    tenant_id: TENANT_ID,
    user_id: USER_ID,
  };
}

function breakdownItems(dimension: UsageBreakdownDimension): UsageBreakdownItem[] {
  const shared = {
    currency: "USD",
    error_count: 1,
    input_tokens: 5480,
    last_used_at: "2026-01-01T09:11:30.000Z",
    output_tokens: 1038,
    request_count: 3,
    success_count: 2,
    total_tokens: 6518,
  };
  const rows: Record<UsageBreakdownDimension, UsageBreakdownItem[]> = {
    agent: [
      {
        ...shared,
        cost_amount: "0.0095",
        dimension,
        key: AGENT_ID,
        label: "E-commerce Customer Service Agent",
      },
    ],
    channel: [
      {
        ...shared,
        cost_amount: "0.0095",
        dimension,
        key: CHANNEL_ID,
        label: "Support Web Widget",
      },
    ],
    cost_center: [
      {
        ...shared,
        cost_amount: "0.0095",
        dimension,
        key: COST_CENTER_ID,
        label: "CS - Customer Success",
      },
    ],
    department: [
      {
        ...shared,
        cost_amount: "0.0095",
        dimension,
        key: DEPARTMENT_ID,
        label: "Customer Success",
      },
    ],
    model: [
      usageBreakdownModel("qwen-plus", "0.0064", 1, 1706, 0),
      usageBreakdownModel("deepseek-v4-flash", "0.0031", 1, 2712, 0),
      usageBreakdownModel("gpt-4o", "0.0000", 1, 2100, 1),
    ],
    status: [
      usageBreakdownStatus("success", "0.0095", 2, 4418, 0),
      usageBreakdownStatus("denied", "0.0000", 1, 2100, 1),
    ],
    user: [
      {
        ...shared,
        cost_amount: "0.0095",
        dimension,
        key: USER_ID,
        label: "Operations Lead",
      },
    ],
  };
  return rows[dimension];
}

function usageBreakdownModel(
  modelKey: string,
  costAmount: string,
  requestCount: number,
  tokens: number,
  errors: number,
): UsageBreakdownItem {
  return {
    cost_amount: costAmount,
    currency: "USD",
    dimension: "model",
    error_count: errors,
    input_tokens: tokens,
    key: modelKey,
    label: modelKey,
    last_used_at: "2026-01-01T09:11:30.000Z",
    output_tokens: 0,
    request_count: requestCount,
    success_count: requestCount - errors,
    total_tokens: tokens,
  };
}

function usageBreakdownStatus(
  status: string,
  costAmount: string,
  requestCount: number,
  tokens: number,
  errors: number,
): UsageBreakdownItem {
  return {
    cost_amount: costAmount,
    currency: "USD",
    dimension: "status",
    error_count: errors,
    input_tokens: tokens,
    key: status,
    label: status,
    last_used_at: "2026-01-01T09:11:30.000Z",
    output_tokens: 0,
    request_count: requestCount,
    success_count: requestCount - errors,
    total_tokens: tokens,
  };
}

function sumCurrency(items: UsageBreakdownItem[]) {
  return items.reduce((total, item) => total + Number(item.cost_amount), 0).toFixed(4);
}
