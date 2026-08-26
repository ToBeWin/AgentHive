import { useCallback, useEffect, useState } from "react";
import { useToast } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import {
  adminApi,
  type BudgetGovernanceTargetsResponse,
  type BudgetLedgerResponse,
  type BudgetPeriod,
  type BudgetPolicyResponse,
  type BudgetPolicyStatus,
  type BudgetPolicyUpsertRequest,
  type BudgetSummaryResponse,
  type UsageBreakdownDimension,
  type UsageBreakdownResponse,
  type UsageLedgerResponse,
} from "../../lib/api";
import {
  createPrototypeBudgetPolicy,
  PROTOTYPE_BUDGET_POLICIES,
  prototypeBudgetExport,
  prototypeBudgetLedger,
  prototypeBudgetSummary,
  prototypeUsageBreakdown,
  prototypeUsageLedger,
  updatePrototypeBudgetPolicyStatus,
} from "./budgetPrototype";
import { type AsyncState, errorToMessage, withRetry } from "./shared";

interface BudgetHookOptions {
  fallbackOnError?: boolean;
}

export function useBudgetSummary(period: BudgetPeriod = "monthly", options: BudgetHookOptions = {}) {
  const [state, setState] = useState<AsyncState<BudgetSummaryResponse>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (options.fallbackOnError) {
      setState({ data: prototypeBudgetSummary(period), error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getBudgetSummary({ period }));
      setState({ data, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [options.fallbackOnError, period]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

export function useBudgetPolicies(options: BudgetHookOptions = {}) {
  const [state, setState] = useState<AsyncState<BudgetPolicyResponse[]>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (options.fallbackOnError) {
      setState({ data: PROTOTYPE_BUDGET_POLICIES, error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getBudgetPolicies());
      setState({ data: data.policies, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [options.fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

const PROTOTYPE_BUDGET_GOVERNANCE_TARGETS: BudgetGovernanceTargetsResponse = {
  agents: [
    {
      description: "Customer service Agent instance for support workflows.",
      id: "00000000-0000-4000-8000-000000000701",
      label: "Customer Service Assistant (customer_service:customer-service, active)",
      metadata: {
        agent_key: "customer_service",
        department_id: "00000000-0000-4000-8000-000000000301",
        module_key: "agent.customer_service",
        visibility: "department",
      },
      status: "active",
    },
  ],
  channels: [
    {
      description: null,
      id: "00000000-0000-4000-8000-000000000801",
      label: "Web Widget (web_widget:default)",
      metadata: {
        agent_id: "00000000-0000-4000-8000-000000000701",
        channel_key: "default",
        channel_type: "web_widget",
      },
      status: "active",
    },
  ],
  cost_centers: [
    {
      description: "Monthly model spend for customer-facing Agent operations.",
      id: "00000000-0000-4000-8000-000000000401",
      label: "CS - Customer Success",
      metadata: {
        code: "CS",
        department_id: "00000000-0000-4000-8000-000000000301",
        monthly_budget_usd: "2500.0000",
      },
      status: "active",
    },
  ],
  departments: [
    {
      description: "Owns customer-facing Agent workflows and knowledge quality.",
      id: "00000000-0000-4000-8000-000000000301",
      label: "Customer Success",
      metadata: {
        parent_id: null,
        sort_order: 10,
      },
      status: null,
    },
  ],
  users: [
    {
      description: null,
      id: "00000000-0000-4000-8000-000000000201",
      label: "Deployment Admin (admin@agenthive.internal)",
      metadata: {
        email: "admin@agenthive.internal",
        is_tenant_admin: true,
      },
      status: "active",
    },
  ],
};

export function useBudgetGovernanceTargets(options: BudgetHookOptions = {}) {
  const [state, setState] = useState<AsyncState<BudgetGovernanceTargetsResponse>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (options.fallbackOnError) {
      setState({ data: PROTOTYPE_BUDGET_GOVERNANCE_TARGETS, error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getBudgetGovernanceTargets());
      setState({ data, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [options.fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

export function useBudgetUsageLedger(options: BudgetHookOptions = {}) {
  const [state, setState] = useState<AsyncState<UsageLedgerResponse>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (options.fallbackOnError) {
      setState({ data: prototypeUsageLedger(), error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getBudgetUsageLedger());
      setState({ data, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [options.fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

export function useBudgetLedger(options: BudgetHookOptions = {}) {
  const [state, setState] = useState<AsyncState<BudgetLedgerResponse>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (options.fallbackOnError) {
      setState({ data: prototypeBudgetLedger(), error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getBudgetLedger());
      setState({ data, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [options.fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

export function useBudgetUsageBreakdown(
  dimension: UsageBreakdownDimension = "department",
  options: BudgetHookOptions = {},
) {
  const [state, setState] = useState<AsyncState<UsageBreakdownResponse>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (options.fallbackOnError) {
      setState({ data: prototypeUsageBreakdown(dimension), error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getBudgetUsageBreakdown(dimension));
      setState({ data, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [dimension, options.fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

export function useBudgetPolicyActions(options: BudgetHookOptions = {}) {
  const { t } = useLocale();
  const { showToast } = useToast();
  const [saving, setSaving] = useState(false);
  const [statusUpdatingPolicyId, setStatusUpdatingPolicyId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const savePolicy = useCallback(
    async (payload: BudgetPolicyUpsertRequest) => {
      setSaving(true);
      setMessage(null);
      setError(null);
      try {
        const response = options.fallbackOnError
          ? createPrototypeBudgetPolicy(payload)
          : await adminApi.saveBudgetPolicy(payload);
        const successMessage = t("budgetsPolicySaved")
          .replace("{{scope}}", response.scope_type)
          .replace("{{type}}", response.budget_type);
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setSaving(false);
      }
    },
    [options.fallbackOnError, showToast, t],
  );

  const updatePolicyStatus = useCallback(
    async (policyId: string, status: BudgetPolicyStatus) => {
      setStatusUpdatingPolicyId(policyId);
      setMessage(null);
      setError(null);
      try {
        const response = options.fallbackOnError
          ? updatePrototypeBudgetPolicyStatus(policyId, status)
          : await adminApi.updateBudgetPolicyStatus(policyId, { status });
        const successMessage = t("budgetsPolicyStatusUpdated");
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setStatusUpdatingPolicyId(null);
      }
    },
    [options.fallbackOnError, showToast, t],
  );

  return { error, message, savePolicy, saving, statusUpdatingPolicyId, updatePolicyStatus };
}

export function prototypeBudgetLedgerExport(format: "csv" | "json", ledger: "budget" | "usage") {
  return prototypeBudgetExport(format, ledger);
}
