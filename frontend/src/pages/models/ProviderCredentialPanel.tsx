import { useState } from "react";
import { ApiNotice, cx, PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type {
  LLMConnectionTestResponse,
  LLMDeploymentAcceptanceTestResponse,
  LLMDeploymentResponse,
  LLMProviderResponse,
} from "../../lib/api";
import { CredentialConfigPanel } from "./CredentialConfigPanel";
import { CredentialDiagnosticsPanel } from "./CredentialDiagnosticsPanel";
import { CredentialRoutesPanel } from "./CredentialRoutesPanel";
import { ModelCredentialProgressPanel } from "./ModelCredentialProgressPanel";
import type { ModelCredentialOwnerOption } from "./modelPolicyScopeOptions";
import { type CredentialFormState, isMediaProvider } from "./modelUtils";
import { ProviderReadinessSummary } from "./ProviderReadinessSummary";

interface ProviderCredentialPanelProps {
  actionError: string | null;
  actionMessage: string | null;
  canWrite: boolean;
  credentialForm: CredentialFormState;
  deploymentsList: LLMDeploymentResponse[];
  lastAcceptanceResult: LLMDeploymentAcceptanceTestResponse | null;
  lastTestResult: LLMConnectionTestResponse | null;
  onAcceptanceTest: () => Promise<boolean>;
  onSaveCredential: () => Promise<boolean>;
  onTestConnection: (options?: { liveCheck?: boolean }) => Promise<boolean>;
  ownerTargetLoading: boolean;
  ownerTargetOptions: ModelCredentialOwnerOption[];
  saving: boolean;
  selectedProvider: LLMProviderResponse | null;
  setCredentialForm: React.Dispatch<React.SetStateAction<CredentialFormState>>;
  testing: boolean;
}

type CredentialWorkspaceTab = "config" | "routes" | "diagnostics";

export function ProviderCredentialPanel({
  actionError,
  actionMessage,
  canWrite,
  credentialForm,
  deploymentsList,
  lastAcceptanceResult,
  lastTestResult,
  onAcceptanceTest,
  onSaveCredential,
  onTestConnection,
  ownerTargetLoading,
  ownerTargetOptions,
  saving,
  selectedProvider,
  setCredentialForm,
  testing,
}: ProviderCredentialPanelProps) {
  const { t } = useLocale();
  const [workspaceTab, setWorkspaceTab] = useState<CredentialWorkspaceTab>("config");
  const credentialDraftReady = Boolean(
    credentialForm.apiKey.trim() && (credentialForm.ownerType === "tenant" || credentialForm.ownerId),
  );
  const canSaveCredential = Boolean(canWrite && credentialDraftReady);
  const providerKey = selectedProvider?.provider_key ?? "";
  const isMedia = isMediaProvider(providerKey);
  const saveCredentialAndShowRoutes = async () => {
    const saved = await onSaveCredential();
    if (saved) {
      setWorkspaceTab("routes");
    }
  };
  const testConnectionAndShowDiagnostics = async (options: { liveCheck?: boolean } = {}) => {
    const tested = await onTestConnection(options);
    if (tested) {
      setWorkspaceTab("diagnostics");
    }
  };
  const runAcceptanceAndShowDiagnostics = async () => {
    const accepted = await onAcceptanceTest();
    if (accepted) {
      setWorkspaceTab("diagnostics");
    }
  };
  return (
    <section className="panel routing-panel model-config-panel" id="model-credential-panel">
      <h2>{t("modelsProviderCredential")}</h2>
      {selectedProvider ? (
        <>
          {!canWrite && (
            <ApiNotice title={t("modelsWritePermissionRequired")} message={t("modelsWritePermissionRequiredDetail")} />
          )}
          <div className="selected-provider">
            <div className="selected-provider-main">
              <strong>{selectedProvider.name}</strong>
              <span>{(selectedProvider.capabilities ?? []).join(" / ") || "chat"}</span>
            </div>
            <dl className="selected-provider-facts">
              <div>
                <dt>{t("modelsProviderType")}</dt>
                <dd>{selectedProvider.adapter_type}</dd>
              </div>
              <div>
                <dt>{t("modelsStatus")}</dt>
                <dd>{providerStatusLabel(selectedProvider.status, t)}</dd>
              </div>
              <div>
                <dt>{t("modelsCredentialState")}</dt>
                <dd>
                  {selectedProvider.credential_configured
                    ? t("modelsCredentialConfigured")
                    : t("modelsCredentialMissing")}
                </dd>
              </div>
              <div>
                <dt>{t("modelsCredentialOwnerType")}</dt>
                <dd>{credentialOwnerLabel(credentialForm.ownerType, t)}</dd>
              </div>
            </dl>
          </div>
          <ProviderReadinessSummary lastTestResult={lastTestResult} provider={selectedProvider} testing={testing} />
          {(actionMessage || actionError) && (
            <div className={cx("form-message", actionError ? "error" : false)}>
              {actionError ? t("modelsProviderActionFailedDetail") : actionMessage}
            </div>
          )}
          <ModelCredentialProgressPanel
            credentialDraftReady={credentialDraftReady}
            deploymentsList={deploymentsList}
            lastAcceptanceResult={lastAcceptanceResult}
            lastTestResult={lastTestResult}
            onSelectTab={setWorkspaceTab}
            selectedProvider={selectedProvider}
            workspaceTab={workspaceTab}
          />
          <PageTabs
            active={workspaceTab}
            onChange={setWorkspaceTab}
            tabs={[
              {
                id: "config",
                label: t("modelsCredentialTabConfig"),
                description: t("modelsCredentialTabConfigDesc"),
              },
              {
                id: "routes",
                label: t("modelsCredentialTabRoutes"),
                description: t("modelsCredentialTabRoutesDesc"),
              },
              {
                id: "diagnostics",
                label: t("modelsCredentialTabDiagnostics"),
                description: t("modelsCredentialTabDiagnosticsDesc"),
              },
            ]}
          />
          {workspaceTab === "config" && (
            <CredentialConfigPanel
              canSaveCredential={canSaveCredential}
              canWrite={canWrite}
              credentialForm={credentialForm}
              onSaveCredential={() => void saveCredentialAndShowRoutes()}
              ownerTargetLoading={ownerTargetLoading}
              ownerTargetOptions={ownerTargetOptions}
              saving={saving}
              selectedProvider={selectedProvider}
              setCredentialForm={setCredentialForm}
            />
          )}
          {workspaceTab === "diagnostics" && (
            <CredentialDiagnosticsPanel
              canWrite={canWrite}
              credentialForm={credentialForm}
              isMedia={isMedia}
              lastAcceptanceResult={lastAcceptanceResult}
              lastTestResult={lastTestResult}
              onAcceptanceTest={() => void runAcceptanceAndShowDiagnostics()}
              onLiveProbe={() => void testConnectionAndShowDiagnostics({ liveCheck: true })}
              onTestConnection={() => void testConnectionAndShowDiagnostics()}
              setCredentialForm={setCredentialForm}
              testing={testing}
            />
          )}
          {workspaceTab === "routes" && <CredentialRoutesPanel deploymentsList={deploymentsList} />}
        </>
      ) : (
        <ApiNotice title={t("modelsNoProviderSelected")} message={t("modelsNoProviderSelectedMessage")} />
      )}
    </section>
  );
}

function providerStatusLabel(status: LLMProviderResponse["status"], t: (key: string) => string) {
  if (status === "active") {
    return t("modelsProviderActive");
  }
  if (status === "not_configured") {
    return t("modelsProviderNotConfigured");
  }
  return t("modelsProviderInactive");
}

function credentialOwnerLabel(ownerType: CredentialFormState["ownerType"], t: (key: string) => string) {
  if (ownerType === "department") {
    return t("modelsCredentialOwnerDepartment");
  }
  if (ownerType === "user") {
    return t("modelsCredentialOwnerUser");
  }
  return t("modelsCredentialOwnerTenant");
}
