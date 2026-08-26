import type { Dispatch, SetStateAction } from "react";
import { PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { LLMModelPriceResponse, LLMPolicyResponse, LLMPolicyStatus } from "../../lib/api";
import { ModelPoliciesPanel } from "./ModelPoliciesPanel";
import { ModelPricesPanel } from "./ModelPricesPanel";
import type { ModelPolicyScopeTargetOption } from "./modelPolicyScopeOptions";
import type { ModelPolicyFormState, ModelPriceFormState } from "./modelUtils";
import type { ModelGovernanceTab } from "./modelWorkspaceTypes";

interface ModelGovernanceWorkspaceProps {
  canWrite: boolean;
  canWritePrices: boolean;
  governanceTab: ModelGovernanceTab;
  onGovernanceTabChange: (tab: ModelGovernanceTab) => void;
  onSavePolicy: () => Promise<boolean>;
  onSavePrice: () => Promise<boolean>;
  onUpdatePolicyStatus: (policyId: string, status: LLMPolicyStatus) => void;
  policiesError: string | null;
  policiesList: LLMPolicyResponse[];
  policiesLoading: boolean;
  policyError: string | null;
  policyForm: ModelPolicyFormState;
  policyMessage: string | null;
  priceError: string | null;
  priceForm: ModelPriceFormState;
  priceMessage: string | null;
  pricesError: string | null;
  pricesList: LLMModelPriceResponse[];
  pricesLoading: boolean;
  refetchPolicies: () => void;
  refetchPrices: () => void;
  savingPolicy: boolean;
  savingPrice: boolean;
  scopeTargetLoading: boolean;
  scopeTargetOptions: ModelPolicyScopeTargetOption[];
  setPolicyForm: Dispatch<SetStateAction<ModelPolicyFormState>>;
  setPriceForm: Dispatch<SetStateAction<ModelPriceFormState>>;
  statusUpdatingPolicyId: string | null;
}

export function ModelGovernanceWorkspace({
  canWrite,
  canWritePrices,
  governanceTab,
  onGovernanceTabChange,
  onSavePolicy,
  onSavePrice,
  onUpdatePolicyStatus,
  policiesError,
  policiesList,
  policiesLoading,
  policyError,
  policyForm,
  policyMessage,
  priceError,
  priceForm,
  priceMessage,
  pricesError,
  pricesList,
  pricesLoading,
  refetchPolicies,
  refetchPrices,
  savingPolicy,
  savingPrice,
  scopeTargetLoading,
  scopeTargetOptions,
  setPolicyForm,
  setPriceForm,
  statusUpdatingPolicyId,
}: ModelGovernanceWorkspaceProps) {
  const { t } = useLocale();

  return (
    <div className="nested-workspace">
      <PageTabs
        active={governanceTab}
        onChange={onGovernanceTabChange}
        tabs={[
          {
            id: "policies",
            label: t("modelsGovernanceTabPolicies"),
            description: t("modelsGovernanceTabPoliciesDesc"),
          },
          {
            id: "prices",
            label: t("modelsGovernanceTabPrices"),
            description: t("modelsGovernanceTabPricesDesc"),
          },
        ]}
      />
      {governanceTab === "policies" && (
        <ModelPoliciesPanel
          onSavePolicy={onSavePolicy}
          onUpdatePolicyStatus={onUpdatePolicyStatus}
          policiesError={policiesError}
          policiesList={policiesList}
          policiesLoading={policiesLoading}
          policyError={policyError}
          policyForm={policyForm}
          policyMessage={policyMessage}
          refetchPolicies={refetchPolicies}
          savingPolicy={savingPolicy}
          canWrite={canWrite}
          setPolicyForm={setPolicyForm}
          scopeTargetLoading={scopeTargetLoading}
          scopeTargetOptions={scopeTargetOptions}
          statusUpdatingPolicyId={statusUpdatingPolicyId}
        />
      )}
      {governanceTab === "prices" && (
        <ModelPricesPanel
          onSavePrice={onSavePrice}
          priceError={priceError}
          priceForm={priceForm}
          priceMessage={priceMessage}
          pricesError={pricesError}
          pricesList={pricesList}
          pricesLoading={pricesLoading}
          refetchPrices={refetchPrices}
          savingPrice={savingPrice}
          canWrite={canWritePrices}
          setPriceForm={setPriceForm}
        />
      )}
    </div>
  );
}
