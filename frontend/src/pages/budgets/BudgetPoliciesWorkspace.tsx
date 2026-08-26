import type React from "react";
import { PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { BudgetPolicyResponse, BudgetPolicyStatus } from "../../lib/api";
import { BudgetGuardrailPanel, BudgetPoliciesPanel } from "./BudgetPanels";
import type { BudgetFormState } from "./budgetUtils";
import type { BudgetPolicyTab } from "./budgetWorkspaceTypes";

interface BudgetPoliciesWorkspaceProps {
  budgetForm: BudgetFormState;
  canSaveBudget: boolean;
  canWrite: boolean;
  onCreate: () => void;
  onPolicyTabChange: (tab: BudgetPolicyTab) => void;
  onRetryPolicies: () => void;
  onSave: () => void;
  onUpdatePolicyStatus: (policyId: string, status: BudgetPolicyStatus) => void;
  policies: BudgetPolicyResponse[];
  policiesError: string | null;
  policiesLoading: boolean;
  policyTab: BudgetPolicyTab;
  saveError: string | null;
  saveMessage: string | null;
  saving: boolean;
  scopeOptions: Array<{ id: string; label: string }>;
  scopeOptionsLoading: boolean;
  setBudgetForm: React.Dispatch<React.SetStateAction<BudgetFormState>>;
  statusUpdatingPolicyId: string | null;
}

export function BudgetPoliciesWorkspace({
  budgetForm,
  canSaveBudget,
  canWrite,
  onCreate,
  onPolicyTabChange,
  onRetryPolicies,
  onSave,
  onUpdatePolicyStatus,
  policies,
  policiesError,
  policiesLoading,
  policyTab,
  saveError,
  saveMessage,
  saving,
  scopeOptions,
  scopeOptionsLoading,
  setBudgetForm,
  statusUpdatingPolicyId,
}: BudgetPoliciesWorkspaceProps) {
  const { t } = useLocale();

  return (
    <div className="nested-workspace">
      <PageTabs
        active={policyTab}
        onChange={onPolicyTabChange}
        tabs={[
          {
            id: "list",
            label: t("budgetsPolicyTabList"),
            description: t("budgetsPolicyTabListDesc"),
          },
          {
            id: "create",
            label: t("budgetsPolicyTabCreate"),
            description: t("budgetsPolicyTabCreateDesc"),
          },
        ]}
      />
      {policyTab === "list" && (
        <BudgetPoliciesPanel
          canWrite={canWrite}
          error={policiesError}
          loading={policiesLoading}
          onCreate={onCreate}
          onRetry={onRetryPolicies}
          onUpdatePolicyStatus={onUpdatePolicyStatus}
          policies={policies}
          statusUpdatingPolicyId={statusUpdatingPolicyId}
        />
      )}
      {policyTab === "create" && (
        <BudgetGuardrailPanel
          budgetForm={budgetForm}
          canSaveBudget={canSaveBudget}
          canWrite={canWrite}
          onSave={onSave}
          saveError={saveError}
          saveMessage={saveMessage}
          saving={saving}
          scopeOptions={scopeOptions}
          scopeOptionsLoading={scopeOptionsLoading}
          setBudgetForm={setBudgetForm}
        />
      )}
    </div>
  );
}
