import { useCallback, useEffect, useState } from "react";
import { type AgentModuleActionResponse, type AgentModuleCatalogEntry, adminApi } from "../../lib/api";
import { getPrototypeSnapshot, runPrototypeAgentModuleAction, usePrototypeSnapshot } from "./prototypeState";
import { type AsyncState, errorToMessage, withRetry } from "./shared";

export function useAgentModules(options: { fallbackOnError?: boolean } = {}) {
  const fallbackOnError = options.fallbackOnError === true;
  const prototypeSnapshot = usePrototypeSnapshot();
  const [state, setState] = useState<AsyncState<AgentModuleCatalogEntry[]>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (fallbackOnError) {
      setState({ data: getPrototypeSnapshot().agentModules, error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getAgentModules());
      setState({ data: data.modules, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  if (fallbackOnError) {
    return { data: prototypeSnapshot.agentModules, error: null, loading: false, refetch: load };
  }

  return { ...state, refetch: load };
}

export function useAgentModuleActions(options: { fallbackOnError?: boolean } = {}) {
  const fallbackOnError = options.fallbackOnError === true;
  const [busyModuleId, setBusyModuleId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runAction = useCallback(
    async (moduleId: string, action: "install" | "enable" | "disable"): Promise<AgentModuleActionResponse | null> => {
      setBusyModuleId(moduleId);
      setMessage(null);
      setError(null);
      if (fallbackOnError) {
        const response = runPrototypeAgentModuleAction(moduleId, action);
        setMessage(response.message);
        setBusyModuleId(null);
        return response;
      }
      try {
        const response =
          action === "install"
            ? await adminApi.installAgentModule(moduleId)
            : action === "enable"
              ? await adminApi.enableAgentModule(moduleId)
              : await adminApi.disableAgentModule(moduleId);
        setMessage(response.message);
        return response;
      } catch (caught) {
        setError(errorToMessage(caught));
        return null;
      } finally {
        setBusyModuleId(null);
      }
    },
    [fallbackOnError],
  );

  const installModule = useCallback((moduleId: string) => runAction(moduleId, "install"), [runAction]);
  const enableModule = useCallback((moduleId: string) => runAction(moduleId, "enable"), [runAction]);
  const disableModule = useCallback((moduleId: string) => runAction(moduleId, "disable"), [runAction]);

  return { busyModuleId, disableModule, enableModule, error, installModule, message };
}
