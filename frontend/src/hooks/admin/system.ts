import { useCallback, useEffect, useMemo, useState } from "react";
import {
  adminApi,
  type ConnectionAcceptanceEvidence,
  type KnowledgeAcceptanceEvidence,
  type SystemHealthReport,
  type SystemInfoResponse,
} from "../../lib/api";
import { getPrototypeSnapshot, usePrototypeSnapshot } from "./prototypeState";
import { type AsyncState, errorToMessage, withRetry } from "./shared";
import { prototypeSystemDiagnostics } from "./systemPrototype";

export interface SystemDiagnostics {
  connection_acceptance?: ConnectionAcceptanceEvidence;
  health: SystemHealthReport;
  info: SystemInfoResponse;
  knowledge_acceptance?: KnowledgeAcceptanceEvidence;
  readiness: SystemHealthReport;
}

export function useSystemDiagnostics(options: { fallbackOnError?: boolean } = {}) {
  const fallbackOnError = options.fallbackOnError === true;
  const prototypeSnapshot = usePrototypeSnapshot();
  const prototypeDiagnostics = useMemo(() => prototypeSystemDiagnostics(prototypeSnapshot), [prototypeSnapshot]);
  const [state, setState] = useState<AsyncState<SystemDiagnostics>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (fallbackOnError) {
      setState({
        data: prototypeSystemDiagnostics(getPrototypeSnapshot()),
        error: null,
        loading: false,
      });
      return;
    }
    try {
      const [health, readiness, info, diagnosticsReport] = await withRetry(() =>
        Promise.all([adminApi.getHealth(), adminApi.getReadiness(), adminApi.getInfo(), adminApi.getDiagnostics()]),
      );
      setState({
        data: {
          connection_acceptance: diagnosticsReport.diagnostics.connection_acceptance as
            | SystemDiagnostics["connection_acceptance"]
            | undefined,
          health,
          info,
          knowledge_acceptance: diagnosticsReport.diagnostics.knowledge_acceptance as
            | SystemDiagnostics["knowledge_acceptance"]
            | undefined,
          readiness,
        },
        error: null,
        loading: false,
      });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  if (fallbackOnError) {
    return { data: prototypeDiagnostics, error: null, loading: false, refetch: load };
  }

  return { ...state, refetch: load };
}
