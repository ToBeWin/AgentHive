import { Button, PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { LLMConnectionTestResponse, LLMDeploymentResponse, LLMProviderResponse } from "../../lib/api";
import { ModelCoveragePanel } from "./ModelCoveragePanel";
import { ModelDeploymentsPanel } from "./ModelDeploymentsPanel";
import type { ModelCoverageTab } from "./modelWorkspaceTypes";
import { ProviderGrid } from "./ProviderGrid";

interface ModelCoverageWorkspaceProps {
  connectedCount: number;
  coverageTab: ModelCoverageTab;
  deploymentsError: string | null;
  deploymentsList: LLMDeploymentResponse[];
  deploymentsLoading: boolean;
  lastTestResult?: LLMConnectionTestResponse | null;
  onCoverageTabChange: (tab: ModelCoverageTab) => void;
  onOpenCredentials: () => void;
  onSelectProvider: (providerKey: string) => void;
  providersError: string | null;
  providersList: LLMProviderResponse[];
  providersLoading: boolean;
  refetchDeployments: () => void;
  refetchProviders: () => void;
  selectedProvider: LLMProviderResponse | null;
  selectedProviderKey: string | null;
  testing?: boolean;
}

export function ModelCoverageWorkspace({
  connectedCount,
  coverageTab,
  deploymentsError,
  deploymentsList,
  deploymentsLoading,
  lastTestResult = null,
  onCoverageTabChange,
  onOpenCredentials,
  onSelectProvider,
  providersError,
  providersList,
  providersLoading,
  refetchDeployments,
  refetchProviders,
  selectedProvider,
  selectedProviderKey,
  testing = false,
}: ModelCoverageWorkspaceProps) {
  const { t } = useLocale();

  return (
    <div className="nested-workspace">
      <ModelCoveragePanel providersList={providersList} />
      <PageTabs
        active={coverageTab}
        onChange={onCoverageTabChange}
        tabs={[
          {
            id: "providers",
            label: t("modelsCoverageTabProviders"),
            description: t("modelsCoverageTabProvidersDesc"),
          },
          {
            id: "deployments",
            label: t("modelsCoverageTabDeployments"),
            description: t("modelsCoverageTabDeploymentsDesc"),
          },
        ]}
      />
      {coverageTab === "providers" && (
        <>
          <ProviderGrid
            providersError={providersError}
            providersList={providersList}
            providersLoading={providersLoading}
            refetchProviders={refetchProviders}
            lastTestResult={lastTestResult}
            selectedProviderKey={selectedProviderKey}
            setSelectedProviderKey={onSelectProvider}
            testing={testing}
          />
          {selectedProvider && (
            <div className="inline-note inline-action-note">
              <span>{t("modelsSelectedProviderReady").replace("{{name}}", selectedProvider.name)}</span>
              <Button onClick={onOpenCredentials}>{t("modelsConfigureSelectedProvider")}</Button>
            </div>
          )}
        </>
      )}
      {coverageTab === "deployments" && (
        <ModelDeploymentsPanel
          connectedCount={connectedCount}
          deploymentsError={deploymentsError}
          deploymentsList={deploymentsList}
          deploymentsLoading={deploymentsLoading}
          providerCount={providersList.length}
          refetchDeployments={refetchDeployments}
        />
      )}
    </div>
  );
}
