import type { Dispatch, SetStateAction } from "react";
import { Button, PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type {
  LLMConnectionTestResponse,
  LLMDeploymentAcceptanceTestResponse,
  LLMDeploymentResponse,
  LLMProviderResponse,
} from "../../lib/api";
import type { ModelCredentialOwnerOption } from "./modelPolicyScopeOptions";
import type { CredentialFormState } from "./modelUtils";
import type { ModelCredentialStage } from "./modelWorkspaceTypes";
import { ProviderCredentialPanel } from "./ProviderCredentialPanel";
import { ProviderGrid } from "./ProviderGrid";

interface ModelCredentialsWorkspaceProps {
  actionError: string | null;
  actionMessage: string | null;
  canWrite: boolean;
  credentialForm: CredentialFormState;
  credentialStage: ModelCredentialStage;
  deploymentsList: LLMDeploymentResponse[];
  lastAcceptanceResult: LLMDeploymentAcceptanceTestResponse | null;
  lastTestResult: LLMConnectionTestResponse | null;
  onAcceptanceTest: () => Promise<boolean>;
  onCredentialStageChange: (stage: ModelCredentialStage) => void;
  onSaveCredential: () => Promise<boolean>;
  onSelectProvider: (providerKey: string) => void;
  onTestConnection: (options?: { liveCheck?: boolean }) => Promise<boolean>;
  ownerTargetLoading: boolean;
  ownerTargetOptions: ModelCredentialOwnerOption[];
  providersError: string | null;
  providersList: LLMProviderResponse[];
  providersLoading: boolean;
  refetchProviders: () => void;
  saving: boolean;
  selectedProvider: LLMProviderResponse | null;
  selectedProviderKey: string | null;
  setCredentialForm: Dispatch<SetStateAction<CredentialFormState>>;
  testing: boolean;
}

export function ModelCredentialsWorkspace({
  actionError,
  actionMessage,
  canWrite,
  credentialForm,
  credentialStage,
  deploymentsList,
  lastAcceptanceResult,
  lastTestResult,
  onAcceptanceTest,
  onCredentialStageChange,
  onSaveCredential,
  onSelectProvider,
  onTestConnection,
  ownerTargetLoading,
  ownerTargetOptions,
  providersError,
  providersList,
  providersLoading,
  refetchProviders,
  saving,
  selectedProvider,
  selectedProviderKey,
  setCredentialForm,
  testing,
}: ModelCredentialsWorkspaceProps) {
  const { t } = useLocale();

  return (
    <div className="nested-workspace model-credential-workspace">
      <PageTabs
        active={credentialStage}
        onChange={onCredentialStageChange}
        tabs={[
          {
            id: "providers",
            label: t("modelsCredentialsStageProviders"),
            description: t("modelsCredentialsStageProvidersDesc"),
          },
          {
            id: "credential",
            label: t("modelsCredentialsStageCredential"),
            description: t("modelsCredentialsStageCredentialDesc"),
          },
        ]}
      />
      {credentialStage === "providers" && (
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
              <Button onClick={() => onCredentialStageChange("credential")}>
                {t("modelsConfigureSelectedProvider")}
              </Button>
            </div>
          )}
        </>
      )}
      {credentialStage === "credential" && (
        <ProviderCredentialPanel
          actionError={actionError}
          actionMessage={actionMessage}
          credentialForm={credentialForm}
          deploymentsList={deploymentsList}
          lastAcceptanceResult={lastAcceptanceResult}
          lastTestResult={lastTestResult}
          onAcceptanceTest={onAcceptanceTest}
          onSaveCredential={onSaveCredential}
          onTestConnection={onTestConnection}
          ownerTargetLoading={ownerTargetLoading}
          ownerTargetOptions={ownerTargetOptions}
          saving={saving}
          selectedProvider={selectedProvider}
          canWrite={canWrite}
          setCredentialForm={setCredentialForm}
          testing={testing}
        />
      )}
    </div>
  );
}
