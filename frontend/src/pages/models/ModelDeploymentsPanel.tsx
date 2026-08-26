import { Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { ApiNotice, Button, EmptyState, Panel, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { LLMDeploymentResponse } from "../../lib/api";

interface ModelDeploymentsPanelProps {
  connectedCount: number;
  deploymentsError: string | null;
  deploymentsList: LLMDeploymentResponse[];
  deploymentsLoading: boolean;
  providerCount: number;
  refetchDeployments: () => void;
}

export function ModelDeploymentsPanel({
  connectedCount,
  deploymentsError,
  deploymentsList,
  deploymentsLoading,
  providerCount,
  refetchDeployments,
}: ModelDeploymentsPanelProps) {
  const { t } = useLocale();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const filteredDeployments = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return deploymentsList.filter((deployment) => {
      const matchesQuery = [
        deployment.display_name,
        deployment.model_key,
        deployment.provider_name,
        deployment.provider_key,
        deployment.routing_key,
        ...deployment.capabilities,
      ]
        .join(" ")
        .toLocaleLowerCase()
        .includes(normalizedQuery);
      return matchesQuery && (statusFilter === "all" || deployment.status === statusFilter);
    });
  }, [deploymentsList, query, statusFilter]);

  return (
    <Panel
      title={t("modelsDeployments")}
      subtitle={`${connectedCount}/${providerCount || 0} ${t("modelsProvidersConfigured")}`}
    >
      {deploymentsError && (
        <ApiNotice
          title={t("modelsDeploymentApiUnavailable")}
          message={deploymentsError}
          action={<Button onClick={refetchDeployments}>{t("commonRetry")}</Button>}
        />
      )}
      <div className="collection-toolbar deployment-table-toolbar">
        <label className="collection-search">
          <Search size={16} aria-hidden="true" />
          <span className="visually-hidden">{t("modelsDeploymentSearchLabel")}</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("modelsDeploymentSearchPlaceholder")}
            aria-label={t("modelsDeploymentSearchLabel")}
          />
          {query && (
            <button
              className="collection-search-clear"
              type="button"
              onClick={() => setQuery("")}
              aria-label={t("commonClearSearch")}
              title={t("commonClearSearch")}
            >
              <X size={14} aria-hidden="true" />
            </button>
          )}
        </label>
        <label className="collection-filter">
          <span>{t("modelsDeploymentFilterLabel")}</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}>
            <option value="all">{t("modelsDeploymentFilterAll")}</option>
            <option value="active">{t("modelsDeploymentFilterActive")}</option>
            <option value="inactive">{t("modelsDeploymentFilterInactive")}</option>
          </select>
        </label>
        <span className="collection-toolbar-meta">
          {t("modelsDeploymentResults")
            .replace("{{visible}}", String(filteredDeployments.length))
            .replace("{{total}}", String(deploymentsList.length))}
        </span>
      </div>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>{t("modelsModelName")}</th>
              <th>{t("modelsProviderType")}</th>
              <th>{t("modelsCapabilities")}</th>
              <th>{t("modelsRoute")}</th>
              <th>{t("modelsStatus")}</th>
              <th>{t("modelsContext")}</th>
            </tr>
          </thead>
          <tbody>
            {deploymentsLoading && (
              <tr>
                <td colSpan={6}>{t("modelsLoadingDeployments")}</td>
              </tr>
            )}
            {!deploymentsLoading && !deploymentsList.length && (
              <tr>
                <td className="table-empty-cell" colSpan={6}>
                  <EmptyState icon={<Search />} title={t("modelsNoDeployments")} />
                </td>
              </tr>
            )}
            {!deploymentsLoading && deploymentsList.length > 0 && !filteredDeployments.length && (
              <tr>
                <td className="table-empty-cell" colSpan={6}>
                  <EmptyState
                    icon={<Search />}
                    title={t("modelsNoDeploymentMatches")}
                    message={t("modelsNoDeploymentMatchesDetail")}
                  />
                </td>
              </tr>
            )}
            {filteredDeployments.map((deployment) => (
              <tr key={deployment.id}>
                <td>
                  <code>{deployment.display_name}</code>
                </td>
                <td>
                  {deployment.provider_name} | {deployment.adapter_type}
                </td>
                <td className="capabilities">{(deployment.capabilities ?? []).join(" ") || "chat"}</td>
                <td>
                  <code>{deployment.routing_key}</code>
                </td>
                <td>
                  <StatusBadge status={deployment.status} />
                </td>
                <td>
                  {deployment.context_window
                    ? `${deployment.context_window.toLocaleString()} tokens`
                    : t("modelsNotSet")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
