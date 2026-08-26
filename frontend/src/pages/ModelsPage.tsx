import { Plus, SlidersHorizontal } from "lucide-react";
import { useEffect } from "react";
import { Button, PageHeader, PageTabs } from "../components/app-ui";
import type { WorkspaceId } from "../data";
import { useLocale } from "../i18n-context";
import type { AuthUser } from "../lib/api";
import { showDeliveryDiagnostics } from "../lib/deliveryDiagnostics";
import { ModelControlLoopPanel } from "./models/ModelControlLoopPanel";
import {
  ModelCoverageWorkspace,
  ModelCredentialsWorkspace,
  ModelDiagnosticsWorkspace,
  ModelGovernanceWorkspace,
} from "./models/ModelWorkspaces";
import { useModelsPageController } from "./models/useModelsPageController";

interface ModelsPageProps {
  activeWorkspace?: WorkspaceId;
  user?: AuthUser | null;
  isPrototype?: boolean;
}

export function ModelsPage({ activeWorkspace = "admin", user = null, isPrototype = false }: ModelsPageProps) {
  const { t } = useLocale();
  const showDiagnostics = showDeliveryDiagnostics(activeWorkspace);
  const models = useModelsPageController({ isPrototype, user });

  useEffect(() => {
    if (!showDiagnostics && models.activeTab === "diagnostics") {
      models.setActiveTab("coverage");
    }
  }, [models.activeTab, models.setActiveTab, showDiagnostics]);

  return (
    <section className="page models-page">
      <PageHeader
        title={t("modelsTitle")}
        subtitle={t("modelsSubtitle")}
        actions={
          <>
            <Button
              onClick={() => models.handleTestConnection()}
              disabled={!models.canWriteModels || !models.selectedProvider || models.testing}
            >
              <SlidersHorizontal size={16} /> {t("modelsTestConnection")}
            </Button>
            <Button
              variant="primary"
              onClick={models.focusEndpointForm}
              disabled={
                !models.canWriteModels ||
                !models.providersList.some((provider) => provider.provider_key === "openai_compatible")
              }
            >
              <Plus size={16} /> {t("modelsAddEndpoint")}
            </Button>
          </>
        }
      />
      {models.localNotice && <div className="form-message">{models.localNotice}</div>}
      {showDiagnostics ? (
        <ModelControlLoopPanel
          activeTab={models.activeTab}
          connectedCount={models.connectedCount}
          connectionHistory={models.connectionHistory ?? []}
          deploymentsList={models.deploymentsList}
          modelReadiness={models.modelReadiness}
          onSelectTab={models.setActiveTab}
          policiesList={models.policiesList}
          pricesCount={models.pricesList.length}
          providersList={models.providersList}
        />
      ) : null}
      <PageTabs
        active={models.activeTab}
        onChange={models.setActiveTab}
        tabs={[
          { id: "coverage", label: t("modelsTabCoverage"), description: t("modelsTabCoverageDesc") },
          { id: "credentials", label: t("modelsTabCredentials"), description: t("modelsTabCredentialsDesc") },
          { id: "governance", label: t("modelsTabGovernance"), description: t("modelsTabGovernanceDesc") },
          ...(showDiagnostics
            ? [
                {
                  id: "diagnostics" as const,
                  label: t("modelsTabDiagnostics"),
                  description: t("modelsTabDiagnosticsDesc"),
                },
              ]
            : []),
        ]}
      />
      {models.activeTab === "coverage" && (
        <ModelCoverageWorkspace
          connectedCount={models.connectedCount}
          coverageTab={models.coverageTab}
          deploymentsError={models.deploymentsError}
          deploymentsList={models.deploymentsList}
          deploymentsLoading={models.deploymentsLoading}
          lastTestResult={models.lastTestResult}
          onCoverageTabChange={models.setCoverageTab}
          onOpenCredentials={() => models.setActiveTab("credentials")}
          onSelectProvider={models.setSelectedProviderKey}
          providersError={models.providersError}
          providersList={models.providersList}
          providersLoading={models.providersLoading}
          refetchDeployments={models.refetchDeployments}
          refetchProviders={models.refetchProviders}
          selectedProvider={models.selectedProvider}
          selectedProviderKey={models.selectedProviderKey}
          testing={models.testing}
        />
      )}
      {models.activeTab === "credentials" && (
        <ModelCredentialsWorkspace
          actionError={models.actionError}
          actionMessage={models.actionMessage}
          canWrite={models.canWriteModels}
          credentialForm={models.credentialForm}
          credentialStage={models.credentialStage}
          deploymentsList={models.selectedProviderDeployments}
          lastAcceptanceResult={models.lastAcceptanceResult}
          lastTestResult={models.lastTestResult}
          onAcceptanceTest={models.handleRunAcceptanceTest}
          onCredentialStageChange={models.setCredentialStage}
          onSaveCredential={models.handleSaveCredential}
          onSelectProvider={models.setSelectedProviderKey}
          onTestConnection={models.handleTestConnection}
          ownerTargetLoading={models.credentialOwnerLoading}
          ownerTargetOptions={models.credentialOwnerOptions}
          providersError={models.providersError}
          providersList={models.providersList}
          providersLoading={models.providersLoading}
          refetchProviders={models.refetchProviders}
          saving={models.saving}
          selectedProvider={models.selectedProvider}
          selectedProviderKey={models.selectedProviderKey}
          setCredentialForm={models.setCredentialForm}
          testing={models.testing}
        />
      )}
      {models.activeTab === "governance" && (
        <ModelGovernanceWorkspace
          canWrite={models.canWriteModels}
          canWritePrices={models.canWriteGlobalPrices}
          governanceTab={models.governanceTab}
          onGovernanceTabChange={models.setGovernanceTab}
          onSavePolicy={models.handleSavePolicy}
          onSavePrice={models.handleSavePrice}
          onUpdatePolicyStatus={models.handleUpdatePolicyStatus}
          policiesError={models.policiesError}
          policiesList={models.policiesList}
          policiesLoading={models.policiesLoading}
          policyError={models.policyError}
          policyForm={models.policyForm}
          policyMessage={models.policyMessage}
          priceError={models.priceError}
          priceForm={models.priceForm}
          priceMessage={models.priceMessage}
          pricesError={models.pricesError}
          pricesList={models.pricesList}
          pricesLoading={models.pricesLoading}
          refetchPolicies={models.refetchPolicies}
          refetchPrices={models.refetchPrices}
          savingPolicy={models.savingPolicy}
          savingPrice={models.savingPrice}
          scopeTargetLoading={models.scopeTargetLoading}
          scopeTargetOptions={models.scopeTargetOptions}
          setPolicyForm={models.setPolicyForm}
          setPriceForm={models.setPriceForm}
          statusUpdatingPolicyId={models.statusUpdatingPolicyId}
        />
      )}
      {models.activeTab === "diagnostics" && (
        <ModelDiagnosticsWorkspace
          connectionHistory={models.connectionHistory ?? []}
          deploymentsList={models.deploymentsList}
          diagnosticsTab={models.diagnosticsTab}
          historyError={models.connectionHistoryError}
          historyLoading={models.connectionHistoryLoading}
          modelReadiness={models.modelReadiness}
          onDiagnosticsTabChange={models.setDiagnosticsTab}
          onOpenCoverage={() => {
            models.setActiveTab("coverage");
            models.setCoverageTab("deployments");
          }}
          onOpenCredentials={() => {
            models.setActiveTab("credentials");
            models.setCredentialStage("credential");
          }}
          onOpenDiagnostics={() => models.setActiveTab("diagnostics")}
          onOpenGovernance={() => {
            models.setActiveTab("governance");
            models.setGovernanceTab("policies");
          }}
          policiesList={models.policiesList}
          pricesCount={models.pricesList.length}
          providersList={models.providersList}
          refetchHistory={models.refetchConnectionHistory}
        />
      )}
    </section>
  );
}
