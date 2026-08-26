import { Button } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { CostCenterFormState } from "./departmentUtils";

interface CostCenterQuickCreatePanelProps {
  costCenterForm: CostCenterFormState;
  onCostCenterFormChange: (form: CostCenterFormState) => void;
  onCreateCostCenter: () => void;
  saving: boolean;
}

export function CostCenterQuickCreatePanel({
  costCenterForm,
  onCostCenterFormChange,
  onCreateCostCenter,
  saving,
}: CostCenterQuickCreatePanelProps) {
  const { t } = useLocale();

  return (
    <div className="org-admin-grid">
      <label>
        {t("departmentsCostCenterName")}
        <input
          value={costCenterForm.name}
          onChange={(event) => onCostCenterFormChange({ ...costCenterForm, name: event.target.value })}
        />
      </label>
      <label>
        {t("departmentsCostCenterCode")}
        <input
          value={costCenterForm.code}
          onChange={(event) => onCostCenterFormChange({ ...costCenterForm, code: event.target.value })}
        />
      </label>
      <label>
        {t("departmentsMonthlyBudget")}
        <input
          value={costCenterForm.monthlyBudget}
          onChange={(event) => onCostCenterFormChange({ ...costCenterForm, monthlyBudget: event.target.value })}
        />
      </label>
      <div className="provider-actions org-actions">
        <Button onClick={onCreateCostCenter} disabled={saving || !costCenterForm.code.trim()}>
          {t("departmentsAddCostCenter")}
        </Button>
      </div>
    </div>
  );
}
