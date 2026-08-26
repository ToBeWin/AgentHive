import { useCallback, useEffect, useRef, useState } from "react";
import {
  type AnalyticsOverviewResponse,
  type AuditLogFilters,
  type AuditLogListResponse,
  adminApi,
} from "../../lib/api";
import { prototypeAuditExport, prototypeAuditLogs } from "./auditPrototype";
import { prototypeAnalyticsOverview } from "./budgetPrototype";
import { type AsyncState, errorToMessage, withRetry } from "./shared";

export function useAnalyticsOverview(options: { fallbackOnError?: boolean } = {}) {
  const [state, setState] = useState<AsyncState<AnalyticsOverviewResponse>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    setState((current) => ({ ...current, error: null, loading: true }));
    if (options.fallbackOnError) {
      setState({ data: prototypeAnalyticsOverview(), error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getAnalyticsOverview());
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

export function useAuditLogs(filters: AuditLogFilters = {}, options: { fallbackOnError?: boolean } = {}) {
  const latestRequestId = useRef(0);
  const [state, setState] = useState<AsyncState<AuditLogListResponse>>({
    data: null,
    error: null,
    loading: true,
  });

  const load = useCallback(async () => {
    const requestId = ++latestRequestId.current;
    setState((current) => ({ ...current, error: null, loading: true }));
    if (options.fallbackOnError) {
      if (requestId === latestRequestId.current) {
        setState({ data: prototypeAuditLogs(filters), error: null, loading: false });
      }
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getAuditLogs(filters));
      if (requestId === latestRequestId.current) {
        setState({ data, error: null, loading: false });
      }
    } catch (error) {
      if (requestId === latestRequestId.current) {
        setState({ data: null, error: errorToMessage(error), loading: false });
      }
    }
  }, [filters, options.fallbackOnError]);

  useEffect(() => {
    void load();
    return () => {
      latestRequestId.current += 1;
    };
  }, [load]);

  return { ...state, refetch: load };
}

export function prototypeAuditLogExport(filters: AuditLogFilters = {}, format: "csv" | "json") {
  return prototypeAuditExport(filters, format);
}
