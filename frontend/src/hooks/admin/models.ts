import { useCallback, useEffect, useState } from "react";
import { useLocale } from "../../i18n-context";
import {
  adminApi,
  type LLMConnectionTestHistoryItem,
  type LLMConnectionTestRequest,
  type LLMConnectionTestResponse,
  type LLMCredentialResponse,
  type LLMCredentialUpsertRequest,
  type LLMDeploymentAcceptanceTestResponse,
  type LLMDeploymentResponse,
  type LLMGovernanceTargetsResponse,
  type LLMModelPriceResponse,
  type LLMModelPriceUpsertRequest,
  type LLMPolicyResponse,
  type LLMPolicyStatus,
  type LLMPolicyUpsertRequest,
  type LLMProviderResponse,
  type LLMReadinessResponse,
} from "../../lib/api";
import {
  createPrototypeAcceptanceTest,
  createPrototypeConnectionTest,
  createPrototypeCredentialResponse,
  createPrototypePolicy,
  createPrototypePrice,
  createPrototypeReadiness,
  PROTOTYPE_MODEL_CONNECTION_TESTS,
  PROTOTYPE_MODEL_DEPLOYMENTS,
  PROTOTYPE_MODEL_POLICIES,
  PROTOTYPE_MODEL_PRICES,
  PROTOTYPE_MODEL_PROVIDERS,
  updatePrototypePolicyStatus,
} from "./modelPrototype";
import { type AsyncState, errorToMessage, withRetry } from "./shared";

interface ModelHookOptions {
  fallbackOnError?: boolean;
}

export function useModelProviders(options: ModelHookOptions = {}) {
  const [state, setState] = useState<AsyncState<LLMProviderResponse[]>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (options.fallbackOnError) {
      setState({ data: PROTOTYPE_MODEL_PROVIDERS, error: null, loading: false });
      return;
    }
    try {
      const data = await adminApi.getModelProviders();
      setState({ data: data.providers, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [options.fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

export function useModelDeployments(options: ModelHookOptions = {}) {
  const [state, setState] = useState<AsyncState<LLMDeploymentResponse[]>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (options.fallbackOnError) {
      setState({ data: PROTOTYPE_MODEL_DEPLOYMENTS, error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getModelDeployments());
      setState({ data: data.deployments, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [options.fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

export function useModelPolicies(options: ModelHookOptions = {}) {
  const [state, setState] = useState<AsyncState<LLMPolicyResponse[]>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (options.fallbackOnError) {
      setState({ data: PROTOTYPE_MODEL_POLICIES, error: null, loading: false });
      return;
    }
    try {
      const data = await adminApi.getModelPolicies();
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

export function useModelPrices(options: ModelHookOptions = {}) {
  const [state, setState] = useState<AsyncState<LLMModelPriceResponse[]>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (options.fallbackOnError) {
      setState({ data: PROTOTYPE_MODEL_PRICES, error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getModelPrices());
      setState({ data: data.prices, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [options.fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

export function useModelConnectionTests(options: ModelHookOptions = {}) {
  const [state, setState] = useState<AsyncState<LLMConnectionTestHistoryItem[]>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (options.fallbackOnError) {
      setState({ data: PROTOTYPE_MODEL_CONNECTION_TESTS, error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getModelConnectionTests(20));
      setState({ data: data.tests, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [options.fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  return { ...state, refetch: load };
}

export function useModelReadiness(options: ModelHookOptions = {}) {
  const [state, setState] = useState<AsyncState<LLMReadinessResponse>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (options.fallbackOnError) {
      setState({ data: createPrototypeReadiness(), error: null, loading: false });
      return;
    }
    try {
      const data = await adminApi.getModelReadiness();
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

const PROTOTYPE_MODEL_GOVERNANCE_TARGETS: LLMGovernanceTargetsResponse = {
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

export function useModelGovernanceTargets(options: ModelHookOptions = {}) {
  const [state, setState] = useState<AsyncState<LLMGovernanceTargetsResponse>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (options.fallbackOnError) {
      setState({ data: PROTOTYPE_MODEL_GOVERNANCE_TARGETS, error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getModelGovernanceTargets());
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

export function useModelCredentialActions(options: ModelHookOptions = {}) {
  const { t } = useLocale();
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastTestResult, setLastTestResult] = useState<LLMConnectionTestResponse | null>(null);
  const [lastAcceptanceResult, setLastAcceptanceResult] = useState<LLMDeploymentAcceptanceTestResponse | null>(null);

  const saveCredential = useCallback(
    async (providerKey: string, payload: LLMCredentialUpsertRequest) => {
      setSaving(true);
      setError(null);
      setMessage(null);
      setLastTestResult(null);
      setLastAcceptanceResult(null);
      try {
        const response: LLMCredentialResponse = options.fallbackOnError
          ? createPrototypeCredentialResponse(providerKey, payload)
          : await adminApi.saveModelCredential(providerKey, payload);
        setMessage(
          t("modelsCredentialSaved")
            .replace("{{name}}", response.display_name)
            .replace("{{secret}}", response.masked_secret),
        );
        return response;
      } catch (caught) {
        setError(errorToMessage(caught));
        return null;
      } finally {
        setSaving(false);
      }
    },
    [options.fallbackOnError, t],
  );

  const testConnection = useCallback(
    async (payload: LLMConnectionTestRequest) => {
      setTesting(true);
      setError(null);
      setMessage(null);
      setLastTestResult(null);
      setLastAcceptanceResult(null);
      try {
        const response: LLMConnectionTestResponse = options.fallbackOnError
          ? createPrototypeConnectionTest(payload)
          : await adminApi.testModelConnection(payload);
        setLastTestResult(response);
        if (response.ok) {
          setMessage(
            t("modelsConnectionAccepted")
              .replace("{{provider}}", response.provider_key ?? payload.provider_key ?? t("modelsUnknownProvider"))
              .replace("{{latency}}", String(response.latency_ms)),
          );
        } else {
          setError(response.message);
        }
        return response;
      } catch (caught) {
        setError(errorToMessage(caught));
        return null;
      } finally {
        setTesting(false);
      }
    },
    [options.fallbackOnError, t],
  );

  const runAcceptanceTest = useCallback(
    async (deploymentId: string) => {
      setTesting(true);
      setError(null);
      setMessage(null);
      setLastAcceptanceResult(null);
      try {
        const response: LLMDeploymentAcceptanceTestResponse = options.fallbackOnError
          ? createPrototypeAcceptanceTest(deploymentId)
          : await adminApi.runDeploymentAcceptanceTest(deploymentId, {});
        setLastAcceptanceResult(response);
        setMessage(
          t("modelsAcceptanceAccepted")
            .replace("{{provider}}", response.provider_key)
            .replace("{{requestId}}", response.request_id),
        );
        return response;
      } catch (caught) {
        setError(errorToMessage(caught));
        return null;
      } finally {
        setTesting(false);
      }
    },
    [options.fallbackOnError, t],
  );

  return {
    error,
    lastAcceptanceResult,
    lastTestResult,
    message,
    runAcceptanceTest,
    saveCredential,
    saving,
    testConnection,
    testing,
  };
}

export function useModelPolicyActions(options: ModelHookOptions = {}) {
  const { t } = useLocale();
  const [saving, setSaving] = useState(false);
  const [statusUpdatingPolicyId, setStatusUpdatingPolicyId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const savePolicy = useCallback(
    async (payload: LLMPolicyUpsertRequest) => {
      setSaving(true);
      setError(null);
      setMessage(null);
      try {
        const response = options.fallbackOnError
          ? createPrototypePolicy(payload)
          : await adminApi.saveModelPolicy(payload);
        setMessage(t("modelsPolicySaved").replace("{{name}}", response.name));
        return response;
      } catch (caught) {
        setError(errorToMessage(caught));
        return null;
      } finally {
        setSaving(false);
      }
    },
    [options.fallbackOnError, t],
  );

  const updatePolicyStatus = useCallback(
    async (policyId: string, status: LLMPolicyStatus) => {
      setStatusUpdatingPolicyId(policyId);
      setError(null);
      setMessage(null);
      try {
        const response = options.fallbackOnError
          ? updatePrototypePolicyStatus(policyId, status)
          : await adminApi.updateModelPolicyStatus(policyId, { status });
        setMessage(t("modelsPolicyStatusUpdated"));
        return response;
      } catch (caught) {
        setError(errorToMessage(caught));
        return null;
      } finally {
        setStatusUpdatingPolicyId(null);
      }
    },
    [options.fallbackOnError, t],
  );

  return { error, message, savePolicy, saving, statusUpdatingPolicyId, updatePolicyStatus };
}

export function useModelPriceActions(options: ModelHookOptions = {}) {
  const { t } = useLocale();
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const savePrice = useCallback(
    async (payload: LLMModelPriceUpsertRequest) => {
      setSaving(true);
      setError(null);
      setMessage(null);
      try {
        const response = options.fallbackOnError
          ? createPrototypePrice(payload)
          : await adminApi.saveModelPrice(payload);
        setMessage(t("modelsPriceSaved").replace("{{model}}", response.model_key));
        return response;
      } catch (caught) {
        setError(errorToMessage(caught));
        return null;
      } finally {
        setSaving(false);
      }
    },
    [options.fallbackOnError, t],
  );

  return { error, message, savePrice, saving };
}
