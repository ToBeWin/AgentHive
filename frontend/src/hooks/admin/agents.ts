import { useCallback, useEffect, useState } from "react";
import { useToast } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import {
  type AgentCatalogEntryResponse,
  type AgentGovernanceTargetsResponse,
  type AgentInstanceCreateRequest,
  type AgentInstanceResponse,
  type AgentInstanceUpdateRequest,
  type AgentRunRequest,
  type AgentRunResponse,
  adminApi,
  type WorkbenchAgentInstanceResponse,
} from "../../lib/api";
import { prototypeAgentRun } from "./prototypeData";
import {
  createPrototypeAgentInstance,
  getPrototypeSnapshot,
  updatePrototypeAgentInstance,
  usePrototypeSnapshot,
} from "./prototypeState";
import { type AsyncState, errorToMessage, withRetry } from "./shared";

function prototypeAgentGovernanceTargets(): AgentGovernanceTargetsResponse {
  const snapshot = getPrototypeSnapshot();
  return {
    departments: [
      {
        description: "Prototype department for Agent ownership and routing.",
        id: "00000000-0000-4000-8000-000000000301",
        label: "Customer Success",
        metadata: { parent_id: null, sort_order: 10 },
      },
    ],
    knowledge_bases: snapshot.knowledgeBases.map((base) => ({
      description: base.description,
      id: base.id,
      label: `${base.name} · ${base.rag_engine}`,
      metadata: {
        document_count: base.document_count,
        name: base.name,
        rag_engine: base.rag_engine,
        status: base.status,
        visibility: base.visibility,
      },
    })),
    model_deployments: [
      {
        description: "Prototype policy default route.",
        id: "00000000-0000-4000-8000-000000000901",
        label: "default-chat · Policy Default",
        metadata: {
          deployment_name: "Policy Default",
          priority: 100,
          routing_key: "default-chat",
        },
      },
    ],
    users: [
      {
        description: "Prototype administrator",
        id: "00000000-0000-4000-8000-000000000201",
        label: "AgentHive Admin (admin@agenthive.local)",
        metadata: { email: "admin@agenthive.local", username: "admin" },
      },
    ],
  };
}

export function useAgentGovernanceTargets(options: { fallbackOnError?: boolean } = {}) {
  const fallbackOnError = options.fallbackOnError === true;
  const [state, setState] = useState<AsyncState<AgentGovernanceTargetsResponse>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (fallbackOnError) {
      setState({ data: prototypeAgentGovernanceTargets(), error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getAgentGovernanceTargets());
      setState({ data, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  if (fallbackOnError) {
    return { data: prototypeAgentGovernanceTargets(), error: null, loading: false, refetch: load };
  }

  return { ...state, refetch: load };
}

export function useAgentCatalog(options: { fallbackOnError?: boolean } = {}) {
  const fallbackOnError = options.fallbackOnError === true;
  const prototypeSnapshot = usePrototypeSnapshot();
  const [state, setState] = useState<AsyncState<AgentCatalogEntryResponse[]>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (fallbackOnError) {
      setState({ data: getPrototypeSnapshot().agentCatalog, error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getAgentCatalog());
      setState({ data: data.agents, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  if (fallbackOnError) {
    return { data: prototypeSnapshot.agentCatalog, error: null, loading: false, refetch: load };
  }

  return { ...state, refetch: load };
}

export function useAgentInstances(options: { fallbackOnError?: boolean } = {}) {
  const fallbackOnError = options.fallbackOnError === true;
  const prototypeSnapshot = usePrototypeSnapshot();
  const [state, setState] = useState<AsyncState<AgentInstanceResponse[]>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (fallbackOnError) {
      setState({ data: getPrototypeSnapshot().agentInstances, error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getAgentInstances());
      setState({ data: data.agents, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  if (fallbackOnError) {
    return { data: prototypeSnapshot.agentInstances, error: null, loading: false, refetch: load };
  }

  return { ...state, refetch: load };
}

export function useWorkbenchAgentInstances(options: { fallbackOnError?: boolean } = {}) {
  const fallbackOnError = options.fallbackOnError === true;
  const prototypeSnapshot = usePrototypeSnapshot();
  const [state, setState] = useState<AsyncState<WorkbenchAgentInstanceResponse[]>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (fallbackOnError) {
      setState({
        data: getPrototypeSnapshot()
          .agentInstances.filter((instance) => instance.status === "active")
          .map(toWorkbenchAgent),
        error: null,
        loading: false,
      });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getWorkbenchAgentInstances());
      setState({ data: data.agents, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  if (fallbackOnError) {
    return {
      data: prototypeSnapshot.agentInstances.filter((instance) => instance.status === "active").map(toWorkbenchAgent),
      error: null,
      loading: false,
      refetch: load,
    };
  }

  return { ...state, refetch: load };
}

function toWorkbenchAgent(instance: AgentInstanceResponse): WorkbenchAgentInstanceResponse {
  const knowledgeBaseRefs = knowledgeBaseRefsFromConfig(instance.config);
  const snapshot = getPrototypeSnapshot();
  const boundKnowledgeBases = knowledgeBaseRefs
    .map((id) => snapshot.knowledgeBases.find((base) => base.id === id && base.status === "active"))
    .filter((base): base is NonNullable<typeof base> => Boolean(base))
    .map((base) => ({
      description: base.description,
      document_count: base.document_count,
      id: base.id,
      name: base.name,
      status: base.status,
      tags: base.tags,
      updated_at: base.updated_at,
      visibility: base.visibility,
    }));
  const modelProfile = instance.model_routing_key || instance.model_key;
  const readinessReasons = [
    ...(modelProfile ? [] : ["model_policy_not_configured"]),
    ...(["customer_service", "data_analyst", "finance", "hr_screening", "report_writer", "store_operations"].includes(
      instance.agent_key,
    ) && knowledgeBaseRefs.length === 0
      ? ["knowledge_not_bound"]
      : []),
  ];
  return {
    agent_key: instance.agent_key,
    department_id: instance.department_id,
    description: instance.description,
    id: instance.id,
    knowledge_base_count: knowledgeBaseRefs.length,
    knowledge_bases: boundKnowledgeBases,
    knowledge_enabled: knowledgeBaseRefs.length > 0,
    model_available: Boolean(modelProfile),
    model_policy: modelProfile ? "configured" : "system_default",
    model_profile: modelProfile || null,
    module_key: instance.module_key,
    name: instance.name,
    readiness: readinessReasons.length ? "needs_configuration" : "ready",
    readiness_reasons: readinessReasons,
    runnable: readinessReasons.length === 0,
    slug: instance.slug,
    status: "active",
    visibility: instance.visibility,
  };
}

function knowledgeBaseRefsFromConfig(config: Record<string, unknown>): string[] {
  const rawIds: unknown[] = [];
  if (config.knowledge_base_id) {
    rawIds.push(config.knowledge_base_id);
  }
  if (Array.isArray(config.knowledge_base_ids)) {
    rawIds.push(...config.knowledge_base_ids);
  }
  return rawIds
    .map((item) => String(item).trim())
    .filter((item, index, list) => item.length > 0 && list.indexOf(item) === index)
    .slice(0, 5);
}

export function useAgentInstanceActions(options: { fallbackOnError?: boolean } = {}) {
  const { t } = useLocale();
  const { showToast } = useToast();
  const fallbackOnError = options.fallbackOnError === true;
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const createAgentInstance = useCallback(
    async (payload: AgentInstanceCreateRequest) => {
      setSaving(true);
      setMessage(null);
      setError(null);
      if (fallbackOnError) {
        const response = createPrototypeAgentInstance(payload);
        setSaving(false);
        const successMessage = t("agentInstancesCreated").replace("{{name}}", response.name);
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      }
      try {
        const response = await adminApi.createAgentInstance(payload);
        const successMessage = t("agentInstancesCreated").replace("{{name}}", response.name);
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
    [fallbackOnError, showToast, t],
  );

  const updateAgentInstance = useCallback(
    async (agentId: string, payload: AgentInstanceUpdateRequest) => {
      setSaving(true);
      setMessage(null);
      setError(null);
      if (fallbackOnError) {
        const response = updatePrototypeAgentInstance(agentId, payload);
        setSaving(false);
        const successMessage = t("agentInstancesUpdated").replace("{{name}}", response.name);
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      }
      try {
        const response = await adminApi.updateAgentInstance(agentId, payload);
        const successMessage = t("agentInstancesUpdated").replace("{{name}}", response.name);
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
    [fallbackOnError, showToast, t],
  );

  return { createAgentInstance, error, message, saving, updateAgentInstance };
}

export function useAgentRunner(options: { fallbackOnError?: boolean } = {}) {
  const fallbackOnError = options.fallbackOnError === true;
  const [running, setRunning] = useState(false);
  const [response, setResponse] = useState<AgentRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(
    async (agentKey: string, payload: AgentRunRequest) => {
      setRunning(true);
      setError(null);
      if (fallbackOnError) {
        const data = prototypeAgentRun(agentKey, payload);
        setResponse(data);
        setRunning(false);
        return data;
      }
      try {
        const data = await adminApi.runAgent(agentKey, payload);
        setResponse(data);
        return data;
      } catch (caught) {
        setError(errorToMessage(caught));
        return null;
      } finally {
        setRunning(false);
      }
    },
    [fallbackOnError],
  );

  return { error, response, run, running };
}
