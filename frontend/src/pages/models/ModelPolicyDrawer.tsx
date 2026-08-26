import { SlidersHorizontal } from "lucide-react";
import type { Dispatch, SetStateAction } from "react";
import { Button, cx, Drawer } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { LLMPolicyEffect, LLMPolicyScope } from "../../lib/api";
import type { ModelPolicyScopeTargetOption } from "./modelPolicyScopeOptions";
import type { ModelPolicyFormState } from "./modelUtils";

interface ModelPolicyDrawerProps {
  canSavePolicy: boolean;
  canWrite: boolean;
  onClose: () => void;
  onSavePolicy: () => Promise<void>;
  policyForm: ModelPolicyFormState;
  savingPolicy: boolean;
  scopeTargetLoading: boolean;
  scopeTargetOptions: ModelPolicyScopeTargetOption[];
  setPolicyForm: Dispatch<SetStateAction<ModelPolicyFormState>>;
  validationMessage: string | null;
}

export function ModelPolicyDrawer({
  canSavePolicy,
  canWrite,
  onClose,
  onSavePolicy,
  policyForm,
  savingPolicy,
  scopeTargetLoading,
  scopeTargetOptions,
  setPolicyForm,
  validationMessage,
}: ModelPolicyDrawerProps) {
  const { t } = useLocale();

  return (
    <Drawer
      open={true}
      title={t("modelsPolicyDrawerTitle")}
      subtitle={t("modelsPolicyDrawerDesc")}
      onClose={onClose}
      ariaLabel={t("modelsPolicyDrawerTitle")}
      className="model-policy-drawer"
      footer={
        <>
          {validationMessage && <span className={cx("form-message", "error")}>{validationMessage}</span>}
          <Button
            variant="primary"
            onClick={() => void onSavePolicy()}
            disabled={!canWrite || savingPolicy || !canSavePolicy}
          >
            <SlidersHorizontal size={16} /> {savingPolicy ? t("modelsSaving") : t("savePolicy")}
          </Button>
        </>
      }
    >
      <div className="model-policy-drawer-content">
        <section className="policy-drawer-section">
          <div className="policy-drawer-section-title">
            <strong>{t("modelsPolicySectionScope")}</strong>
            <span>{t("modelsPolicySectionScopeDesc")}</span>
          </div>
          <div className="policy-form-grid">
            <label>
              {t("modelsPolicyName")}
              <input
                disabled={!canWrite}
                value={policyForm.name}
                onChange={(event) => updatePolicy(setPolicyForm, "name", event.target.value)}
              />
            </label>
            <label>
              {t("modelsScope")}
              <select
                disabled={!canWrite}
                value={policyForm.scopeType}
                onChange={(event) => updatePolicyScope(setPolicyForm, event.target.value as LLMPolicyScope)}
              >
                <option value="tenant">{formatPolicyScope("tenant", t)}</option>
                <option value="department">{formatPolicyScope("department", t)}</option>
                <option value="cost_center">{formatPolicyScope("cost_center", t)}</option>
                <option value="user">{formatPolicyScope("user", t)}</option>
                <option value="agent">{formatPolicyScope("agent", t)}</option>
                <option value="channel">{formatPolicyScope("channel", t)}</option>
              </select>
            </label>
            {policyForm.scopeType !== "tenant" && (
              <label>
                {t("modelsScopeId")}
                <select
                  disabled={!canWrite || scopeTargetLoading || !scopeTargetOptions.length}
                  value={policyForm.scopeId}
                  onChange={(event) => updatePolicy(setPolicyForm, "scopeId", event.target.value)}
                >
                  <option value="">
                    {scopeTargetLoading
                      ? t("modelsLoadingScopeTargets")
                      : scopeTargetOptions.length
                        ? t("modelsSelectScopeTarget")
                        : t("modelsNoScopeTargets")}
                  </option>
                  {scopeTargetOptions.map((option) => (
                    <option key={option.id} value={option.id}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <label>
              {t("modelsEffect")}
              <select
                disabled={!canWrite}
                value={policyForm.effect}
                onChange={(event) => updatePolicy(setPolicyForm, "effect", event.target.value as LLMPolicyEffect)}
              >
                <option value="allow">{t("modelsAllow")}</option>
                <option value="deny">{t("modelsDeny")}</option>
              </select>
            </label>
          </div>
        </section>

        <section className="policy-drawer-section">
          <div className="policy-drawer-section-title">
            <strong>{t("modelsPolicySectionRoutes")}</strong>
            <span>{t("modelsPolicySectionRoutesDesc")}</span>
          </div>
          <div className="policy-form-grid">
            <label>
              {t("modelsAllowedModels")}
              <input
                disabled={!canWrite}
                placeholder={t("modelsModelKeyPlaceholder")}
                value={policyForm.allowedModels}
                onChange={(event) => updatePolicy(setPolicyForm, "allowedModels", event.target.value)}
              />
            </label>
            <label>
              {t("modelsAllowedRoutes")}
              <input
                disabled={!canWrite}
                placeholder={t("modelsRoutingKeyPlaceholder")}
                value={policyForm.allowedRoutingKeys}
                onChange={(event) => updatePolicy(setPolicyForm, "allowedRoutingKeys", event.target.value)}
              />
            </label>
            <label>
              {t("modelsDefaultModel")}
              <input
                disabled={!canWrite}
                placeholder={t("modelsModelKeyPlaceholder")}
                value={policyForm.defaultModelKey}
                onChange={(event) => updatePolicy(setPolicyForm, "defaultModelKey", event.target.value)}
              />
            </label>
            <label>
              {t("modelsDefaultRoute")}
              <input
                disabled={!canWrite}
                placeholder={t("modelsRoutingKeyPlaceholder")}
                value={policyForm.defaultRoutingKey}
                onChange={(event) => updatePolicy(setPolicyForm, "defaultRoutingKey", event.target.value)}
              />
            </label>
          </div>
        </section>

        <section className="policy-drawer-section">
          <div className="policy-drawer-section-title">
            <strong>{t("modelsPolicySectionLimits")}</strong>
            <span>{t("modelsPolicySectionLimitsDesc")}</span>
          </div>
          <div className="policy-form-grid">
            <label>
              {t("modelsMaxTokens")}
              <input
                disabled={!canWrite}
                inputMode="numeric"
                min="1"
                step="1"
                type="number"
                value={policyForm.maxTokens}
                onChange={(event) => updatePolicy(setPolicyForm, "maxTokens", event.target.value)}
              />
            </label>
            <label>
              {t("modelsPolicyPriority")}
              <input
                disabled={!canWrite}
                inputMode="numeric"
                min="1"
                step="1"
                type="number"
                value={policyForm.priority}
                onChange={(event) => updatePolicy(setPolicyForm, "priority", event.target.value)}
              />
            </label>
          </div>
        </section>
      </div>
    </Drawer>
  );
}

function updatePolicy<K extends keyof ModelPolicyFormState>(
  setPolicyForm: Dispatch<SetStateAction<ModelPolicyFormState>>,
  key: K,
  value: ModelPolicyFormState[K],
) {
  setPolicyForm((current) => ({ ...current, [key]: value }));
}

function updatePolicyScope(setPolicyForm: Dispatch<SetStateAction<ModelPolicyFormState>>, scopeType: LLMPolicyScope) {
  setPolicyForm((current) => ({ ...current, scopeId: "", scopeType }));
}

export function formatPolicyScope(scope: LLMPolicyScope, t: (key: string) => string) {
  const suffix = scope
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
  return t(`budgetsScope${suffix}`);
}
