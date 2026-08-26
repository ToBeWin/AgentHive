import { ApiNotice, Button, Panel, StatusBadge } from "../../components/app-ui";
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
                <td colSpan={6}>{t("modelsNoDeployments")}</td>
              </tr>
            )}
            {deploymentsList.map((deployment) => (
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
