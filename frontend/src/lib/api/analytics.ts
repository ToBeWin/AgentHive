import { apiGet } from "./core";

export interface AnalyticsTotals {
  total_requests: number;
  total_tokens: number;
  total_cost_usd: number;
  success_rate: number;
}

export interface ModelUsageItem {
  model_key: string;
  tokens: number;
  cost_usd: number;
  requests: number;
}

export interface DailyUsageItem {
  date: string;
  tokens: number;
  cost_usd: number;
  requests: number;
}

export interface DepartmentUsageItem {
  department_id: string | null;
  department_name: string;
  tokens: number;
  cost_usd: number;
  requests: number;
}

export interface UserUsageItem {
  user_id: string | null;
  user_name: string;
  tokens: number;
  cost_usd: number;
  requests: number;
}

export interface AgentUsageItem {
  agent_id: string | null;
  agent_name: string;
  agent_key: string | null;
  tokens: number;
  cost_usd: number;
  requests: number;
}

export interface AnalyticsOverviewResponse {
  totals: AnalyticsTotals;
  model_usage: ModelUsageItem[];
  daily_usage: DailyUsageItem[];
  department_usage: DepartmentUsageItem[];
  user_usage: UserUsageItem[];
  agent_usage: AgentUsageItem[];
  generated_at: string;
  metadata: Record<string, string>;
}

export const analyticsApi = {
  getAnalyticsOverview: () => apiGet<AnalyticsOverviewResponse>("/api/v1/analytics/overview"),
};
