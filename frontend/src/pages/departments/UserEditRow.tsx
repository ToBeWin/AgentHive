import { useMemo, useState } from "react";
import { Button } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type {
  CostCenterResponse,
  DepartmentResponse,
  RoleResponse,
  UserResponse,
  UserUpdateRequest,
} from "../../lib/api";

type UserEditForm = {
  costCenterId: string;
  departmentId: string;
  email: string;
  fullName: string;
  isLeader: boolean;
  isTenantAdmin: boolean;
  phone: string;
  positionTitle: string;
  roleId: string;
};

export function UserEditRow({
  costCenters,
  departments,
  onCancel,
  onSave,
  roles,
  saving,
  user,
}: {
  costCenters: CostCenterResponse[];
  departments: DepartmentResponse[];
  onCancel: () => void;
  onSave: (userId: string, payload: UserUpdateRequest) => Promise<boolean>;
  roles: RoleResponse[];
  saving: boolean;
  user: UserResponse;
}) {
  const { t } = useLocale();
  const primaryDepartment = user.departments.find((binding) => binding.is_primary) ?? user.departments[0] ?? null;
  const primaryRole = user.roles[0] ?? null;
  const [form, setForm] = useState<UserEditForm>({
    costCenterId: primaryDepartment?.cost_center_id ?? "",
    departmentId: primaryDepartment?.department_id ?? departments[0]?.id ?? "",
    email: user.email,
    fullName: user.full_name ?? "",
    isLeader: primaryDepartment?.is_leader ?? false,
    isTenantAdmin: user.is_tenant_admin,
    phone: user.phone ?? "",
    positionTitle: primaryDepartment?.position_title ?? "",
    roleId: primaryRole?.id ?? roles[0]?.id ?? "",
  });

  const selectableCostCenters = useMemo(
    () =>
      costCenters.filter(
        (costCenter) =>
          !costCenter.department_id || !form.departmentId || costCenter.department_id === form.departmentId,
      ),
    [costCenters, form.departmentId],
  );

  const save = async () => {
    const payload: UserUpdateRequest = {
      email: form.email.trim(),
      full_name: form.fullName.trim() || null,
      is_tenant_admin: form.isTenantAdmin,
      phone: form.phone.trim() || null,
      role_ids: form.roleId ? [form.roleId] : [],
      username: null,
    };
    if (form.departmentId) {
      payload.department_bindings = [
        {
          cost_center_id: form.costCenterId || null,
          department_id: form.departmentId,
          is_leader: form.isLeader,
          is_primary: true,
          position_title: form.positionTitle.trim() || null,
        },
      ];
    } else {
      payload.department_bindings = [];
    }
    const saved = await onSave(user.id, payload);
    if (saved) {
      onCancel();
    }
  };

  return (
    <div className="user-edit-row">
      <div className="user-edit-grid">
        <label>
          {t("departmentsNewUserEmail")}
          <input value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
        </label>
        <label>
          {t("departmentsNewUserName")}
          <input value={form.fullName} onChange={(event) => setForm({ ...form, fullName: event.target.value })} />
        </label>
        <label>
          {t("departmentsUserPhone")}
          <input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
        </label>
        <label>
          {t("departmentsNewUserRole")}
          <select value={form.roleId} onChange={(event) => setForm({ ...form, roleId: event.target.value })}>
            <option value="">{t("departmentsNoRoleSelected")}</option>
            {roles.map((role) => (
              <option key={role.id} value={role.id}>
                {role.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("departmentsDepartmentColumn")}
          <select
            value={form.departmentId}
            onChange={(event) => setForm({ ...form, costCenterId: "", departmentId: event.target.value })}
          >
            <option value="">{t("departmentsUnassigned")}</option>
            {departments.map((department) => (
              <option key={department.id} value={department.id}>
                {department.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("departmentsNewUserCostCenter")}
          <select
            value={form.costCenterId}
            onChange={(event) => setForm({ ...form, costCenterId: event.target.value })}
          >
            <option value="">{t("departmentsNoCostCenterSelected")}</option>
            {selectableCostCenters.map((costCenter) => (
              <option key={costCenter.id} value={costCenter.id}>
                {costCenter.code} - {costCenter.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("departmentsPositionTitle")}
          <input
            value={form.positionTitle}
            onChange={(event) => setForm({ ...form, positionTitle: event.target.value })}
          />
        </label>
        <label className="inline-check">
          <input
            checked={form.isLeader}
            type="checkbox"
            onChange={(event) => setForm({ ...form, isLeader: event.target.checked })}
          />
          {t("departmentsDepartmentLeader")}
        </label>
        <label className="inline-check">
          <input
            checked={form.isTenantAdmin}
            type="checkbox"
            onChange={(event) => setForm({ ...form, isTenantAdmin: event.target.checked })}
          />
          {t("departmentsTenantAdmin")}
        </label>
      </div>
      <div className="user-edit-actions">
        <Button onClick={save} disabled={saving || !form.email.trim()}>
          {saving ? t("departmentsSavingUser") : t("departmentsSaveUser")}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={saving}>
          {t("departmentsCancelUserEdit")}
        </Button>
      </div>
    </div>
  );
}
