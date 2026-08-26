import { ChevronDown, KeyRound } from "lucide-react";
import type { Dispatch, ReactNode, SetStateAction } from "react";
import { Button } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { LLMProviderResponse } from "../../lib/api";
import type { ModelCredentialOwnerOption } from "./modelPolicyScopeOptions";
import {
  type CredentialFormState,
  type CredentialOwnerType,
  defaultModelKeyForProvider,
  defaultRoutingKeyForProvider,
  isMediaProvider,
  modelKeyPlaceholderForProvider,
  providerCredentialHintKey,
  providerProtocolLabelKey,
  routingKeyPlaceholderForProvider,
} from "./modelUtils";

interface CredentialConfigPanelProps {
  canSaveCredential: boolean;
  canWrite: boolean;
  credentialForm: CredentialFormState;
  onSaveCredential: () => void;
  ownerTargetLoading: boolean;
  ownerTargetOptions: ModelCredentialOwnerOption[];
  saving: boolean;
  selectedProvider: LLMProviderResponse;
  setCredentialForm: Dispatch<SetStateAction<CredentialFormState>>;
}

export function CredentialConfigPanel({
  canSaveCredential,
  canWrite,
  credentialForm,
  onSaveCredential,
  ownerTargetLoading,
  ownerTargetOptions,
  saving,
  selectedProvider,
  setCredentialForm,
}: CredentialConfigPanelProps) {
  const { t } = useLocale();
  const providerKey = selectedProvider.provider_key;
  const isMedia = isMediaProvider(providerKey);
  const protocolLabel = t(providerProtocolLabelKey(selectedProvider));
  const defaultModelKey = defaultModelKeyForProvider(providerKey);
  const defaultRoutingKey = defaultRoutingKeyForProvider(providerKey);

  return (
    <>
      <section className="credential-protocol-hint" aria-label={t("modelsCredentialProtocolTitle")}>
        <div>
          <span>{t("modelsCredentialProtocolTitle")}</span>
          <strong>{protocolLabel}</strong>
          <small>{t(providerCredentialHintKey(selectedProvider))}</small>
        </div>
        <dl>
          <div>
            <dt>{t("modelsModelKey")}</dt>
            <dd>{defaultModelKey}</dd>
          </div>
          <div>
            <dt>{t("modelsRoutingKey")}</dt>
            <dd>{defaultRoutingKey}</dd>
          </div>
        </dl>
      </section>
      <CredentialSection
        defaultOpen
        description={t("modelsCredentialConnectionDesc")}
        title={t("modelsCredentialConnection")}
      >
        <label>
          {t("modelsDisplayName")}
          <input
            disabled={!canWrite}
            value={credentialForm.displayName}
            onChange={(event) => updateCredential(setCredentialForm, "displayName", event.target.value)}
          />
        </label>
        <label>
          {t("modelsApiKey")}
          <input
            autoComplete="off"
            disabled={!canWrite}
            placeholder={t("modelsApiKeyPlaceholder")}
            type="password"
            value={credentialForm.apiKey}
            onChange={(event) => updateCredential(setCredentialForm, "apiKey", event.target.value)}
          />
        </label>
        <label>
          {t("modelsBaseUrl")}
          <input
            disabled={!canWrite}
            placeholder={t(isMedia ? "modelsMediaBaseUrlPlaceholder" : "modelsBaseUrlPlaceholder")}
            value={credentialForm.baseUrl}
            onChange={(event) => updateCredential(setCredentialForm, "baseUrl", event.target.value)}
          />
        </label>
      </CredentialSection>
      <CredentialSection description={t("modelsCredentialScopeDesc")} title={t("modelsCredentialScope")}>
        <div className="credential-owner-grid">
          <label>
            {t("modelsCredentialOwnerType")}
            <select
              disabled={!canWrite}
              value={credentialForm.ownerType}
              onChange={(event) =>
                updateCredentialOwnerType(setCredentialForm, event.target.value as CredentialOwnerType)
              }
            >
              <option value="tenant">{t("modelsCredentialOwnerTenant")}</option>
              <option value="department">{t("modelsCredentialOwnerDepartment")}</option>
              <option value="user">{t("modelsCredentialOwnerUser")}</option>
            </select>
          </label>
          {credentialForm.ownerType !== "tenant" && (
            <label>
              {t("modelsCredentialOwnerId")}
              <select
                disabled={!canWrite || ownerTargetLoading || !ownerTargetOptions.length}
                value={credentialForm.ownerId}
                onChange={(event) => updateCredential(setCredentialForm, "ownerId", event.target.value)}
              >
                <option value="">
                  {ownerTargetLoading
                    ? t("modelsLoadingCredentialOwners")
                    : ownerTargetOptions.length
                      ? t("modelsSelectCredentialOwner")
                      : t("modelsNoCredentialOwners")}
                </option>
                {ownerTargetOptions.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      </CredentialSection>
      <CredentialSection description={t("modelsCredentialDeploymentDesc")} title={t("modelsCredentialDeployment")}>
        <label>
          {t("modelsModelKey")}
          <input
            disabled={!canWrite}
            placeholder={modelKeyPlaceholderForProvider(providerKey)}
            value={credentialForm.modelKey}
            onChange={(event) => updateCredential(setCredentialForm, "modelKey", event.target.value)}
          />
        </label>
        <label>
          {t("modelsRoutingKey")}
          <input
            disabled={!canWrite}
            placeholder={routingKeyPlaceholderForProvider(providerKey)}
            value={credentialForm.routingKey}
            onChange={(event) => updateCredential(setCredentialForm, "routingKey", event.target.value)}
          />
        </label>
        <label>
          {t("modelsDeploymentName")}
          <input
            disabled={!canWrite}
            placeholder={t(isMedia ? "modelsMediaDeploymentNamePlaceholder" : "modelsDeploymentNamePlaceholder")}
            value={credentialForm.deploymentName}
            onChange={(event) => updateCredential(setCredentialForm, "deploymentName", event.target.value)}
          />
        </label>
      </CredentialSection>
      <div className="provider-actions">
        <Button onClick={onSaveCredential} disabled={!canWrite || saving || !canSaveCredential}>
          <KeyRound size={16} /> {saving ? t("modelsSaving") : t("modelsSaveKey")}
        </Button>
      </div>
    </>
  );
}

function CredentialSection({
  children,
  defaultOpen = false,
  description,
  title,
}: {
  children: ReactNode;
  defaultOpen?: boolean;
  description: string;
  title: string;
}) {
  return (
    <details className="credential-section" open={defaultOpen}>
      <summary>
        <span>
          <strong>{title}</strong>
          <small>{description}</small>
        </span>
        <ChevronDown size={16} />
      </summary>
      <div className="credential-section-body">{children}</div>
    </details>
  );
}

function updateCredential<K extends keyof CredentialFormState>(
  setCredentialForm: Dispatch<SetStateAction<CredentialFormState>>,
  key: K,
  value: CredentialFormState[K],
) {
  setCredentialForm((current) => ({ ...current, [key]: value }));
}

function updateCredentialOwnerType(
  setCredentialForm: Dispatch<SetStateAction<CredentialFormState>>,
  ownerType: CredentialOwnerType,
) {
  setCredentialForm((current) => ({ ...current, ownerId: "", ownerType }));
}
