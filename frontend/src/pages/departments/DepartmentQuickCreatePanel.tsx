import { Button } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { DepartmentFormState } from "./departmentUtils";

interface DepartmentQuickCreatePanelProps {
  departmentForm: DepartmentFormState;
  onCreateDepartment: () => void;
  onDepartmentFormChange: (form: DepartmentFormState) => void;
  saving: boolean;
}

export function DepartmentQuickCreatePanel({
  departmentForm,
  onCreateDepartment,
  onDepartmentFormChange,
  saving,
}: DepartmentQuickCreatePanelProps) {
  const { t } = useLocale();

  return (
    <div className="org-admin-grid">
      <label>
        {t("departmentsDepartmentName")}
        <input
          value={departmentForm.name}
          onChange={(event) => onDepartmentFormChange({ ...departmentForm, name: event.target.value })}
        />
      </label>
      <label>
        {t("departmentsDepartmentDescription")}
        <input
          placeholder={t("departmentsDepartmentDescriptionPlaceholder")}
          value={departmentForm.description}
          onChange={(event) => onDepartmentFormChange({ ...departmentForm, description: event.target.value })}
        />
      </label>
      <div className="provider-actions org-actions">
        <Button onClick={onCreateDepartment} disabled={saving || !departmentForm.name.trim()}>
          {t("departmentsAddDepartment")}
        </Button>
      </div>
    </div>
  );
}
