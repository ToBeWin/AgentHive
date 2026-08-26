import { Layers, PauseCircle, PlayCircle, Plus } from "lucide-react";
import { useState } from "react";
import { ApiNotice, Button, cx, EmptyState, Panel, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { LLMPolicyResponse, LLMPolicyStatus } from "../../lib/api";
import { formatPolicyScope, ModelPolicyDrawer } from "./ModelPolicyDrawer";
import type { ModelPolicyScopeTargetOption } from "./modelPolicyScopeOptions";
import { defaultModelPolicyForm, type ModelPolicyFormState, modelPolicyValidationKey } from "./modelUtils";

interface ModelPoliciesPanelProps {
  canWrite: boolean;
  onSavePolicy: () => Promise<boolean>;
  onUpdatePolicyStatus: (policyId: string, status: LLMPolicyStatus) => void;
  policiesError: string | null;
  policiesList: LLMPolicyResponse[];
  policiesLoading: boolean;
  policyError: string | null;
  policyForm: ModelPolicyFormState;
  policyMessage: string | null;
  refetchPolicies: () => void;
  savingPolicy: boolean;
  setPolicyForm: React.Dispatch<React.SetStateAction<ModelPolicyFormState>>;
  scopeTargetLoading: boolean;
  scopeTargetOptions: ModelPolicyScopeTargetOption[];
  statusUpdatingPolicyId: string | null;
}

export function ModelPoliciesPanel({
  canWrite,
  onSavePolicy,
  onUpdatePolicyStatus,
  policiesError,
  policiesList,
  policiesLoading,
  policyError,
  policyForm,
  policyMessage,
  refetchPolicies,
  savingPolicy,
  setPolicyForm,
  scopeTargetLoading,
  scopeTargetOptions,
  statusUpdatingPolicyId,
}: ModelPoliciesPanelProps) {
  const { t } = useLocale();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const activePolicyCount = policiesList.filter((policy) => policy.status === "active").length;
  const validationKey = modelPolicyValidationKey(policyForm, { scopeTargetLoading, scopeTargetOptions });
  const canSavePolicy = Boolean(canWrite && !validationKey);
  const openCreatePolicy = () => {
    setPolicyForm(defaultModelPolicyForm());
    setDrawerOpen(true);
  };
  const savePolicyAndCloseDrawer = async () => {
    const saved = await onSavePolicy();
    if (saved) {
      setPolicyForm(defaultModelPolicyForm());
      setDrawerOpen(false);
    }
  };
  return (
    <Panel
      title={t("modelsPolicies")}
      subtitle={`${activePolicyCount} ${t("modelsActiveRules")}`}
      actions={
        canWrite ? (
          <Button onClick={openCreatePolicy}>
            <Plus size={16} /> {t("modelsPolicyWorkspaceCreate")}
          </Button>
        ) : undefined
      }
      className="model-policy-panel"
    >
      {policiesError && (
        <ApiNotice
          title={t("modelsPolicyApiUnavailable")}
          message={policiesError}
          action={<Button onClick={refetchPolicies}>{t("commonRetry")}</Button>}
        />
      )}
      {!canWrite && (
        <ApiNotice title={t("modelsWritePermissionRequired")} message={t("modelsWritePermissionRequiredDetail")} />
      )}
      {(policyMessage || policyError) && (
        <div className={cx("form-message", policyError ? "error" : false)}>{policyError ?? policyMessage}</div>
      )}
      <div className="table-scroll">
        <table className="data-table compact-table">
          <thead>
            <tr>
              <th>{t("modelsRule")}</th>
              <th>{t("modelsScope")}</th>
              <th>{t("modelsEffect")}</th>
              <th>{t("modelsStatus")}</th>
              <th>{t("modelsPolicyModels")}</th>
              <th>{t("modelsMax")}</th>
              <th>{t("modelsActions")}</th>
            </tr>
          </thead>
          <tbody>
            {policiesLoading && (
              <tr>
                <td colSpan={7}>{t("modelsLoadingPolicies")}</td>
              </tr>
            )}
            {!policiesLoading && !policiesList.length && (
              <tr>
                <td className="table-empty-cell" colSpan={7}>
                  <EmptyState
                    icon={<Layers />}
                    title={t("modelsNoPolicies")}
                    action={canWrite && <Button onClick={openCreatePolicy}>{t("modelsPolicyWorkspaceCreate")}</Button>}
                  />
                </td>
              </tr>
            )}
            {policiesList.map((policy) => {
              const nextStatus: LLMPolicyStatus = policy.status === "active" ? "inactive" : "active";
              const updating = statusUpdatingPolicyId === policy.id;
              return (
                <tr key={policy.id}>
                  <td>{policy.name}</td>
                  <td>
                    {formatPolicyScope(policy.scope_type, t)}
                    {policy.scope_id ? `:${policy.scope_id.slice(0, 8)}` : ""}
                  </td>
                  <td>
                    <StatusBadge status={policy.effect.toUpperCase()} />
                  </td>
                  <td>
                    <StatusBadge status={policy.status} />
                  </td>
                  <td className="capabilities">
                    {(policy.allowed_models ?? []).join(" ") || policy.default_model_key || "*"}
                  </td>
                  <td>{policy.max_tokens ? policy.max_tokens.toLocaleString() : t("modelsNoCap")}</td>
                  <td>
                    <Button
                      variant="ghost"
                      disabled={!canWrite || updating}
                      onClick={() => onUpdatePolicyStatus(policy.id, nextStatus)}
                    >
                      {nextStatus === "active" ? <PlayCircle size={16} /> : <PauseCircle size={16} />}
                      {updating
                        ? t("modelsUpdatingPolicy")
                        : nextStatus === "active"
                          ? t("modelsActivatePolicy")
                          : t("modelsDeactivatePolicy")}
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {drawerOpen && (
        <ModelPolicyDrawer
          canSavePolicy={canSavePolicy}
          canWrite={canWrite}
          onClose={() => setDrawerOpen(false)}
          onSavePolicy={savePolicyAndCloseDrawer}
          policyForm={policyForm}
          savingPolicy={savingPolicy}
          scopeTargetLoading={scopeTargetLoading}
          scopeTargetOptions={scopeTargetOptions}
          setPolicyForm={setPolicyForm}
          validationMessage={validationKey ? t(validationKey) : null}
        />
      )}
    </Panel>
  );
}
