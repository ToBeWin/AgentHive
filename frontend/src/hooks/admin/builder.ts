import { useCallback, useEffect, useState } from "react";
import { useLocale } from "../../i18n-context";
import {
  type AgentBuilderConfig,
  type AgentInstanceResponse,
  adminApi,
  type BuilderPreviewResponse,
  type BuilderValidateResponse,
  type McpServerResponse,
} from "../../lib/api";
import { type AsyncState, errorToMessage, withRetry } from "./shared";

export function useMcpServers(options: { fallbackOnError?: boolean } = {}) {
  const fallbackOnError = options.fallbackOnError === true;
  const [state, setState] = useState<AsyncState<McpServerResponse[]>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (fallbackOnError) {
      setState({ data: [], error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.listServers());
      setState({ data: data.servers, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  if (fallbackOnError) {
    return { data: [] as McpServerResponse[], error: null, loading: false, refetch: load };
  }

  return { ...state, refetch: load };
}

interface BuilderActionsState {
  validating: boolean;
  previewing: boolean;
  saving: boolean;
  error: string | null;
  message: string | null;
  validation: BuilderValidateResponse | null;
  preview: BuilderPreviewResponse | null;
  savedInstance: AgentInstanceResponse | null;
}

export function useBuilderActions(options: { fallbackOnError?: boolean } = {}) {
  const { t } = useLocale();
  const fallbackOnError = options.fallbackOnError === true;
  const [state, setState] = useState<BuilderActionsState>({
    validating: false,
    previewing: false,
    saving: false,
    error: null,
    message: null,
    validation: null,
    preview: null,
    savedInstance: null,
  });

  const validate = useCallback(
    async (config: AgentBuilderConfig) => {
      setState((current) => ({ ...current, validating: true, error: null, validation: null }));
      if (fallbackOnError) {
        const fake: BuilderValidateResponse = { ok: true, issues: [] };
        setState((current) => ({ ...current, validating: false, validation: fake }));
        return fake;
      }
      try {
        const data = await adminApi.validate(config);
        setState((current) => ({ ...current, validating: false, validation: data }));
        return data;
      } catch (caught) {
        setState((current) => ({
          ...current,
          validating: false,
          error: errorToMessage(caught),
        }));
        return null;
      }
    },
    [fallbackOnError],
  );

  const runPreview = useCallback(
    async (config: AgentBuilderConfig) => {
      setState((current) => ({ ...current, previewing: true, error: null, preview: null }));
      if (fallbackOnError) {
        const fake: BuilderPreviewResponse = {
          ok: true,
          issues: [],
          rendered: {
            system_prompt: config.system_prompt,
            user_prompt_template: "{{input}}",
            response_style: config.response_style,
            language: config.language,
            greeting_message: config.greeting_message ?? null,
            fallback_message: config.fallback_message ?? "Sorry, I cannot help with that.",
            escalation_message: config.escalation_message ?? null,
            confidence_threshold: config.confidence_threshold ?? null,
            bound_knowledge_base_ids: config.knowledge_base_ids ?? [],
            bound_mcp_server_keys: config.mcp_server_keys ?? [],
            runtime_metadata: { source: "low_code_builder", preview: true },
          },
        };
        setState((current) => ({ ...current, previewing: false, preview: fake }));
        return fake;
      }
      try {
        const data = await adminApi.preview({ config });
        setState((current) => ({ ...current, previewing: false, preview: data }));
        return data;
      } catch (caught) {
        setState((current) => ({
          ...current,
          previewing: false,
          error: errorToMessage(caught),
        }));
        return null;
      }
    },
    [fallbackOnError],
  );

  const createInstance = useCallback(
    async (config: AgentBuilderConfig) => {
      setState((current) => ({ ...current, saving: true, error: null, savedInstance: null }));
      if (fallbackOnError) {
        const fakeInstance: AgentInstanceResponse = {
          id: `proto-builder-${Date.now()}`,
          tenant_id: "prototype",
          name: config.name,
          slug: config.name.toLowerCase().replace(/\s+/g, "-"),
          agent_key: "custom_builder",
          module_key: "agent.custom_builder",
          description: config.description ?? null,
          status: "active",
          visibility: "tenant",
          department_id: null,
          owner_user_id: null,
          model_routing_key: config.routing_key ?? null,
          model_key: config.model_key ?? null,
          system_prompt: config.system_prompt,
          config: { builder_config: { config } },
          metadata: { source: "low_code_builder" },
          created_by: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          runnable: true,
          readiness: "ready",
          readiness_reasons: [],
          model_available: true,
          knowledge_base_count: config.knowledge_base_ids?.length ?? 0,
          knowledge_enabled: (config.knowledge_base_ids?.length ?? 0) > 0,
        };
        setState((current) => ({
          ...current,
          saving: false,
          savedInstance: fakeInstance,
          message: t("builderCreated").replace("{{name}}", fakeInstance.name),
        }));
        return fakeInstance;
      }
      try {
        const data = await adminApi.createInstance(config);
        setState((current) => ({
          ...current,
          saving: false,
          savedInstance: data,
          message: t("builderCreated").replace("{{name}}", data.name),
        }));
        return data;
      } catch (caught) {
        setState((current) => ({
          ...current,
          saving: false,
          error: errorToMessage(caught),
        }));
        return null;
      }
    },
    [fallbackOnError, t],
  );

  const updateInstance = useCallback(
    async (agentId: string, config: AgentBuilderConfig) => {
      setState((current) => ({ ...current, saving: true, error: null, savedInstance: null }));
      if (fallbackOnError) {
        const fakeInstance: AgentInstanceResponse = {
          id: agentId,
          tenant_id: "prototype",
          name: config.name,
          slug: config.name.toLowerCase().replace(/\s+/g, "-"),
          agent_key: "custom_builder",
          module_key: "agent.custom_builder",
          description: config.description ?? null,
          status: "active",
          visibility: "tenant",
          department_id: null,
          owner_user_id: null,
          model_routing_key: config.routing_key ?? null,
          model_key: config.model_key ?? null,
          system_prompt: config.system_prompt,
          config: { builder_config: { config } },
          metadata: { source: "low_code_builder" },
          created_by: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          runnable: true,
          readiness: "ready",
          readiness_reasons: [],
          model_available: true,
          knowledge_base_count: config.knowledge_base_ids?.length ?? 0,
          knowledge_enabled: (config.knowledge_base_ids?.length ?? 0) > 0,
        };
        setState((current) => ({
          ...current,
          saving: false,
          savedInstance: fakeInstance,
          message: t("builderUpdated").replace("{{name}}", fakeInstance.name),
        }));
        return fakeInstance;
      }
      try {
        const data = await adminApi.updateInstance(agentId, config);
        setState((current) => ({
          ...current,
          saving: false,
          savedInstance: data,
          message: t("builderUpdated").replace("{{name}}", data.name),
        }));
        return data;
      } catch (caught) {
        setState((current) => ({
          ...current,
          saving: false,
          error: errorToMessage(caught),
        }));
        return null;
      }
    },
    [fallbackOnError, t],
  );

  const reset = useCallback(() => {
    setState({
      validating: false,
      previewing: false,
      saving: false,
      error: null,
      message: null,
      validation: null,
      preview: null,
      savedInstance: null,
    });
  }, []);

  // Clear only the validation result so field edits don't keep the save button
  // locked by a stale failed-validation report. Preserves messages/savedInstance.
  const clearValidation = useCallback(() => {
    setState((current) => (current.validation === null ? current : { ...current, validation: null }));
  }, []);

  return {
    ...state,
    validate,
    runPreview,
    createInstance,
    updateInstance,
    reset,
    clearValidation,
  };
}
