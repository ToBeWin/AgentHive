import { useEffect, useMemo, useState } from "react";
import { Button, ConfirmDialog, PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type {
  CostCenterResponse,
  CostCenterUpdateRequest,
  DepartmentResponse,
  DepartmentUpdateRequest,
} from "../../lib/api";

type DepartmentEditForm = {
  description: string;
  name: string;
  sortOrder: string;
};

type CostCenterEditForm = {
  code: string;
  departmentId: string;
  description: string;
  isActive: boolean;
  monthlyBudget: string;
  name: string;
};

type GovernanceEditorTab = "department" | "cost";

export function OrgGovernancePanel({
  costCenters,
  departments,
  onDeleteCostCenter,
  onDeleteDepartment,
  onUpdateCostCenter,
  onUpdateDepartment,
  saving,
  selectedDepartment,
}: {
  costCenters: CostCenterResponse[];
  departments: DepartmentResponse[];
  onDeleteCostCenter: (costCenterId: string) => Promise<boolean>;
  onDeleteDepartment: (departmentId: string) => Promise<boolean>;
  onUpdateCostCenter: (costCenterId: string, payload: CostCenterUpdateRequest) => Promise<boolean>;
  onUpdateDepartment: (departmentId: string, payload: DepartmentUpdateRequest) => Promise<boolean>;
  saving: boolean;
  selectedDepartment: DepartmentResponse | null;
}) {
  const { t } = useLocale();
  const [editorTab, setEditorTab] = useState<GovernanceEditorTab>("department");
  const [pendingDeleteDepartment, setPendingDeleteDepartment] = useState<DepartmentResponse | null>(null);
  const [pendingDeleteCostCenter, setPendingDeleteCostCenter] = useState<CostCenterResponse | null>(null);
  const selectedCostCenter = useMemo(
    () =>
      costCenters.find((costCenter) => costCenter.department_id === selectedDepartment?.id) ??
      costCenters.find((costCenter) => costCenter.department_id === null) ??
      costCenters[0] ??
      null,
    [costCenters, selectedDepartment?.id],
  );
  const [departmentForm, setDepartmentForm] = useState<DepartmentEditForm>(() => departmentToForm(selectedDepartment));
  const [costCenterForm, setCostCenterForm] = useState<CostCenterEditForm>(() => costCenterToForm(selectedCostCenter));

  useEffect(() => {
    setDepartmentForm(departmentToForm(selectedDepartment));
  }, [selectedDepartment]);

  useEffect(() => {
    setCostCenterForm(costCenterToForm(selectedCostCenter));
  }, [selectedCostCenter]);

  const saveDepartment = async () => {
    if (!selectedDepartment) {
      return;
    }
    await onUpdateDepartment(selectedDepartment.id, {
      description: departmentForm.description.trim() || null,
      name: departmentForm.name.trim(),
      parent_id: selectedDepartment.parent_id,
      sort_order: Number(departmentForm.sortOrder || selectedDepartment.sort_order),
    });
  };

  const deleteDepartment = () => {
    if (!selectedDepartment) {
      return;
    }
    setPendingDeleteDepartment(selectedDepartment);
  };

  const confirmDeleteDepartment = async () => {
    const target = pendingDeleteDepartment;
    setPendingDeleteDepartment(null);
    if (!target) {
      return;
    }
    await onDeleteDepartment(target.id);
  };

  const saveCostCenter = async () => {
    if (!selectedCostCenter) {
      return;
    }
    await onUpdateCostCenter(selectedCostCenter.id, {
      code: costCenterForm.code.trim(),
      department_id: costCenterForm.departmentId || null,
      description: costCenterForm.description.trim() || null,
      is_active: costCenterForm.isActive,
      monthly_budget_usd: costCenterForm.monthlyBudget.trim() || null,
      name: costCenterForm.name.trim(),
    });
  };

  const deleteCostCenter = () => {
    if (!selectedCostCenter) {
      return;
    }
    setPendingDeleteCostCenter(selectedCostCenter);
  };

  const confirmDeleteCostCenter = async () => {
    const target = pendingDeleteCostCenter;
    setPendingDeleteCostCenter(null);
    if (!target) {
      return;
    }
    await onDeleteCostCenter(target.id);
  };

  return (
    <section className="mini-panel org-governance-panel">
      <div className="panel-title compact">
        <h3>{t("departmentsGovernancePanel")}</h3>
        <span>{t("departmentsGovernancePanelHint")}</span>
      </div>
      <div className="org-governance-editor">
        <PageTabs
          active={editorTab}
          onChange={setEditorTab}
          tabs={[
            {
              id: "department",
              label: t("departmentsDepartmentSettings"),
              description: t("departmentsDepartmentSettingsDesc"),
            },
            {
              id: "cost",
              label: t("departmentsCostCenterSettings"),
              description: t("departmentsCostCenterSettingsDesc"),
            },
          ]}
        />
        {editorTab === "department" && (
          <div className="org-governance-card">
            <h4>{t("departmentsDepartmentSettings")}</h4>
            {!selectedDepartment ? (
              <span>{t("departmentsNoDepartmentSelected")}</span>
            ) : (
              <>
                <label>
                  {t("departmentsDepartmentName")}
                  <input
                    value={departmentForm.name}
                    onChange={(event) => setDepartmentForm({ ...departmentForm, name: event.target.value })}
                  />
                </label>
                <label>
                  {t("departmentsDepartmentDescription")}
                  <input
                    value={departmentForm.description}
                    onChange={(event) => setDepartmentForm({ ...departmentForm, description: event.target.value })}
                  />
                </label>
                <label>
                  {t("departmentsSortOrder")}
                  <input
                    inputMode="numeric"
                    value={departmentForm.sortOrder}
                    onChange={(event) => setDepartmentForm({ ...departmentForm, sortOrder: event.target.value })}
                  />
                </label>
                <div className="role-card-actions">
                  <Button onClick={saveDepartment} disabled={saving || !departmentForm.name.trim()}>
                    {t("departmentsSaveDepartment")}
                  </Button>
                  <Button variant="ghost" onClick={deleteDepartment} disabled={saving}>
                    {t("departmentsDeleteDepartment")}
                  </Button>
                </div>
              </>
            )}
          </div>
        )}
        {editorTab === "cost" && (
          <div className="org-governance-card">
            <h4>{t("departmentsCostCenterSettings")}</h4>
            {!selectedCostCenter ? (
              <span>{t("departmentsNoCostCenters")}</span>
            ) : (
              <>
                <label>
                  {t("departmentsCostCenterCode")}
                  <input
                    value={costCenterForm.code}
                    onChange={(event) => setCostCenterForm({ ...costCenterForm, code: event.target.value })}
                  />
                </label>
                <label>
                  {t("departmentsCostCenterName")}
                  <input
                    value={costCenterForm.name}
                    onChange={(event) => setCostCenterForm({ ...costCenterForm, name: event.target.value })}
                  />
                </label>
                <label>
                  {t("departmentsMonthlyBudget")}
                  <input
                    value={costCenterForm.monthlyBudget}
                    onChange={(event) => setCostCenterForm({ ...costCenterForm, monthlyBudget: event.target.value })}
                  />
                </label>
                <label>
                  {t("departmentsDepartmentColumn")}
                  <select
                    value={costCenterForm.departmentId}
                    onChange={(event) => setCostCenterForm({ ...costCenterForm, departmentId: event.target.value })}
                  >
                    <option value="">{t("departmentsTenantWide")}</option>
                    {departments.map((department) => (
                      <option key={department.id} value={department.id}>
                        {department.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="inline-check">
                  <input
                    checked={costCenterForm.isActive}
                    type="checkbox"
                    onChange={(event) => setCostCenterForm({ ...costCenterForm, isActive: event.target.checked })}
                  />
                  {t("departmentsCostCenterActive")}
                </label>
                <div className="role-card-actions">
                  <Button onClick={saveCostCenter} disabled={saving || !costCenterForm.code.trim()}>
                    {t("departmentsSaveCostCenter")}
                  </Button>
                  <Button variant="ghost" onClick={deleteCostCenter} disabled={saving}>
                    {t("departmentsDeleteCostCenter")}
                  </Button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
      <ConfirmDialog
        open={Boolean(pendingDeleteDepartment)}
        title={t("departmentsDeleteDepartment")}
        message={
          pendingDeleteDepartment
            ? t("departmentsDeleteDepartmentConfirm").replace("{{department}}", pendingDeleteDepartment.name)
            : ""
        }
        confirmLabel={t("departmentsDeleteDepartment")}
        cancelLabel={t("commonClose")}
        variant="danger"
        onConfirm={confirmDeleteDepartment}
        onCancel={() => setPendingDeleteDepartment(null)}
      />
      <ConfirmDialog
        open={Boolean(pendingDeleteCostCenter)}
        title={t("departmentsDeleteCostCenter")}
        message={
          pendingDeleteCostCenter
            ? t("departmentsDeleteCostCenterConfirm").replace("{{costCenter}}", pendingDeleteCostCenter.code)
            : ""
        }
        confirmLabel={t("departmentsDeleteCostCenter")}
        cancelLabel={t("commonClose")}
        variant="danger"
        onConfirm={confirmDeleteCostCenter}
        onCancel={() => setPendingDeleteCostCenter(null)}
      />
    </section>
  );
}

function departmentToForm(department: DepartmentResponse | null): DepartmentEditForm {
  return {
    description: department?.description ?? "",
    name: department?.name ?? "",
    sortOrder: String(department?.sort_order ?? 0),
  };
}

function costCenterToForm(costCenter: CostCenterResponse | null): CostCenterEditForm {
  return {
    code: costCenter?.code ?? "",
    departmentId: costCenter?.department_id ?? "",
    description: costCenter?.description ?? "",
    isActive: costCenter?.is_active ?? true,
    monthlyBudget: costCenter?.monthly_budget_usd ?? "",
    name: costCenter?.name ?? "",
  };
}
