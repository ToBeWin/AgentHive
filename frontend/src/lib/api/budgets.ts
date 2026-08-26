import { apiDownloadText, apiGet, apiPatch, apiPost } from "./core";

export type BudgetScopeType = "tenant" | "department" | "cost_center" | "user" | "agent" | "channel";
export type BudgetPeriod = "daily" | "monthly" | "custom";
export type BudgetLimitType = "hard" | "soft";
export type BudgetPolicyStatus = "active" | "inactive";
export type BudgetLimitHealth = "ok" | "warning" | "exceeded";
export type BudgetEventType = "reserve" | "settle" | "release" | "deny" | "alert";
export type UsageBreakdownDimension = "department" | "user" | "cost_center" | "agent" | "channel" | "model" | "status";

export interface BudgetPolicyUpsertRequest {
  id?: string | null;
  name?: string | null;
  description?: string | null;
  scope_type: BudgetScopeType;
  scope_id?: string | null;
  period: BudgetPeriod;
  custom_period_start?: string | null;
  custom_period_end?: string | null;
  budget_type: BudgetLimitType;
  currency: string;
  amount_limit: string | number;
  token_limit?: number | null;
  alert_threshold_pct: number;
  status: BudgetPolicyStatus;
}

export interface BudgetPolicyStatusUpdateRequest {
  status: BudgetPolicyStatus;
}

export interface BudgetPolicyResponse {
  id: string;
  tenant_id: string;
  name: string | null;
  description: string | null;
  scope_type: BudgetScopeType;
  scope_id: string | null;
  period: BudgetPeriod;
  custom_period_start: string | null;
  custom_period_end: string | null;
  budget_type: BudgetLimitType;
  currency: string;
  amount_limit: string;
  amount_spent: string;
  token_limit: number | null;
  tokens_used: number;
  alert_threshold_pct: number;
  status: BudgetPolicyStatus;
  health: BudgetLimitHealth;
  created_at: string;
  updated_at: string;
}

export interface BudgetPolicyListResponse {
  policies: BudgetPolicyResponse[];
}

export interface BudgetGovernanceTargetItem {
  id: string;
  label: string;
  description: string | null;
  status: string | null;
  metadata: Record<string, unknown>;
}

export interface BudgetGovernanceTargetsResponse {
  departments: BudgetGovernanceTargetItem[];
  cost_centers: BudgetGovernanceTargetItem[];
  users: BudgetGovernanceTargetItem[];
  agents: BudgetGovernanceTargetItem[];
  channels: BudgetGovernanceTargetItem[];
}

export interface BudgetScopeSummary {
  scope_type: BudgetScopeType;
  policy_count: number;
  active_policy_count: number;
  amount_limit: string;
  amount_spent: string;
  token_limit: number | null;
  tokens_used: number;
}

export interface BudgetSummaryResponse {
  tenant_id: string;
  currency: string;
  period: BudgetPeriod;
  period_start: string;
  period_end: string;
  generated_at: string;
  policy_count: number;
  active_policy_count: number;
  hard_policy_count: number;
  soft_policy_count: number;
  warning_policy_count: number;
  exceeded_policy_count: number;
  total_amount_limit: string;
  total_amount_spent: string;
  total_token_limit: number | null;
  total_tokens_used: number;
  by_scope: BudgetScopeSummary[];
  metadata: Record<string, unknown>;
}

export interface BudgetSummaryFilters {
  period?: BudgetPeriod;
  period_start?: string | null;
  period_end?: string | null;
}

export interface UsageLedgerFilters {
  limit?: number;
  start?: string | null;
  end?: string | null;
  user_id?: string | null;
  department_id?: string | null;
  cost_center_id?: string | null;
  agent_id?: string | null;
  channel_id?: string | null;
  model_key?: string | null;
  status?: string | null;
}

export interface UsageLedgerItem {
  id: string;
  tenant_id: string;
  created_at: string;
  deployment_id: string | null;
  user_id: string | null;
  department_id: string | null;
  agent_id: string | null;
  channel_id: string | null;
  conversation_id: string | null;
  cost_center_id: string | null;
  request_id: string;
  model_key: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_amount: string;
  currency: string;
  status: string;
  error_code: string | null;
  metadata: Record<string, unknown>;
}

export interface UsageLedgerResponse {
  items: UsageLedgerItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface BudgetLedgerItem {
  id: string;
  tenant_id: string;
  created_at: string;
  budget_id: string | null;
  reservation_id: string;
  request_id: string;
  event_type: BudgetEventType;
  scope_type: BudgetScopeType;
  scope_id: string | null;
  user_id: string | null;
  department_id: string | null;
  cost_center_id: string | null;
  agent_id: string | null;
  channel_id: string | null;
  conversation_id: string | null;
  estimated_tokens: number;
  actual_tokens: number;
  estimated_cost_amount: string;
  actual_cost_amount: string;
  currency: string;
  reason: string | null;
  metadata: Record<string, unknown>;
}

export interface BudgetLedgerResponse {
  items: BudgetLedgerItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface BudgetLedgerFilters {
  limit?: number;
  start?: string | null;
  end?: string | null;
  budget_id?: string | null;
  reservation_id?: string | null;
  request_id?: string | null;
  event_type?: BudgetEventType | null;
  scope_type?: BudgetScopeType | null;
  scope_id?: string | null;
  user_id?: string | null;
  department_id?: string | null;
  cost_center_id?: string | null;
  agent_id?: string | null;
  channel_id?: string | null;
}

export interface UsageBreakdownItem {
  dimension: UsageBreakdownDimension;
  key: string;
  label: string | null;
  request_count: number;
  success_count: number;
  error_count: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_amount: string;
  currency: string;
  last_used_at: string | null;
}

export interface UsageBreakdownResponse {
  tenant_id: string;
  dimension: UsageBreakdownDimension;
  period_start: string | null;
  period_end: string | null;
  items: UsageBreakdownItem[];
  total_request_count: number;
  total_cost_amount: string;
  total_tokens: number;
}

export const budgetsApi = {
  getBudgetSummary: (filters: BudgetSummaryFilters = {}) => {
    const params = new URLSearchParams();
    if (filters.period) {
      params.set("period", filters.period);
    }
    if (filters.period_start) {
      params.set("period_start", filters.period_start);
    }
    if (filters.period_end) {
      params.set("period_end", filters.period_end);
    }
    const query = params.toString();
    return apiGet<BudgetSummaryResponse>(`/api/v1/budgets/summary${query ? `?${query}` : ""}`);
  },
  getBudgetPolicies: () => apiGet<BudgetPolicyListResponse>("/api/v1/budgets/policies"),
  getBudgetGovernanceTargets: () => apiGet<BudgetGovernanceTargetsResponse>("/api/v1/budgets/governance-targets"),
  getBudgetLedger: () => apiGet<BudgetLedgerResponse>("/api/v1/budgets/budget-ledger?limit=12"),
  getBudgetUsageLedger: () => apiGet<UsageLedgerResponse>("/api/v1/budgets/usage-ledger?limit=12"),
  getBudgetUsageBreakdown: (dimension: UsageBreakdownDimension = "department") =>
    apiGet<UsageBreakdownResponse>(`/api/v1/budgets/usage-breakdown?dimension=${dimension}&limit=8`),
  exportBudgetLedgerCsv: (filters: BudgetLedgerFilters = {}) => {
    const params = budgetLedgerParams({ ...filters, limit: filters.limit ?? 5000 });
    return apiDownloadText(`/api/v1/budgets/budget-ledger/export?${params.toString()}`);
  },
  exportBudgetLedgerJson: (filters: BudgetLedgerFilters = {}) => {
    const params = budgetLedgerParams({ ...filters, limit: filters.limit ?? 5000 });
    params.set("format", "json");
    return apiDownloadText(`/api/v1/budgets/budget-ledger/export?${params.toString()}`);
  },
  exportUsageLedgerCsv: (filters: UsageLedgerFilters = {}) => {
    const params = usageLedgerParams({ ...filters, limit: filters.limit ?? 5000 });
    return apiDownloadText(`/api/v1/budgets/usage-ledger/export?${params.toString()}`);
  },
  exportUsageLedgerJson: (filters: UsageLedgerFilters = {}) => {
    const params = usageLedgerParams({ ...filters, limit: filters.limit ?? 5000 });
    params.set("format", "json");
    return apiDownloadText(`/api/v1/budgets/usage-ledger/export?${params.toString()}`);
  },
  saveBudgetPolicy: (payload: BudgetPolicyUpsertRequest) =>
    apiPost<BudgetPolicyResponse, BudgetPolicyUpsertRequest>("/api/v1/budgets/policies", payload),
  updateBudgetPolicyStatus: (policyId: string, payload: BudgetPolicyStatusUpdateRequest) =>
    apiPatch<BudgetPolicyResponse, BudgetPolicyStatusUpdateRequest>(
      `/api/v1/budgets/policies/${policyId}/status`,
      payload,
    ),
};

function usageLedgerParams(filters: UsageLedgerFilters) {
  const params = new URLSearchParams();
  params.set("limit", String(filters.limit ?? 50));
  for (const key of [
    "start",
    "end",
    "user_id",
    "department_id",
    "cost_center_id",
    "agent_id",
    "channel_id",
    "model_key",
    "status",
  ] as const) {
    const value = filters[key]?.trim();
    if (value) {
      params.set(key, value);
    }
  }
  return params;
}

function budgetLedgerParams(filters: BudgetLedgerFilters) {
  const params = new URLSearchParams();
  params.set("limit", String(filters.limit ?? 50));
  for (const key of [
    "start",
    "end",
    "budget_id",
    "reservation_id",
    "request_id",
    "event_type",
    "scope_type",
    "scope_id",
    "user_id",
    "department_id",
    "cost_center_id",
    "agent_id",
    "channel_id",
  ] as const) {
    const value = filters[key]?.trim();
    if (value) {
      params.set(key, value);
    }
  }
  return params;
}
