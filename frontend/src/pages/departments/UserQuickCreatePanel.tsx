import { useState } from "react";
import { Button, PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { CostCenterResponse, RoleResponse } from "../../lib/api";
import type { UserFormState } from "./departmentUtils";
import type { UserCreateTab } from "./orgSetupTypes";

interface UserQuickCreatePanelProps {
  onCreateUser: () => void;
  onUserFormChange: (form: UserFormState) => void;
  roles: RoleResponse[];
  saving: boolean;
  selectableCostCenters: CostCenterResponse[];
  userForm: UserFormState;
}

export function UserQuickCreatePanel({
  onCreateUser,
  onUserFormChange,
  roles,
  saving,
  selectableCostCenters,
  userForm,
}: UserQuickCreatePanelProps) {
  const { t } = useLocale();
  const [userCreateTab, setUserCreateTab] = useState<UserCreateTab>("identity");

  return (
    <div className="org-user-create">
      <PageTabs
        active={userCreateTab}
        onChange={setUserCreateTab}
        tabs={[
          {
            id: "identity",
            label: t("departmentsUserIdentityTab"),
            description: t("departmentsUserIdentityTabDesc"),
          },
          {
            id: "access",
            label: t("departmentsUserAccessTab"),
            description: t("departmentsUserAccessTabDesc"),
          },
        ]}
      />
      <div className="org-admin-grid">
        {userCreateTab === "identity" && (
          <>
            <label>
              {t("departmentsNewUserEmail")}
              <input
                value={userForm.email}
                onChange={(event) => onUserFormChange({ ...userForm, email: event.target.value })}
              />
            </label>
            <label>
              {t("departmentsNewUserName")}
              <input
                value={userForm.fullName}
                onChange={(event) => onUserFormChange({ ...userForm, fullName: event.target.value })}
              />
            </label>
            <label>
              {t("departmentsInitialPassword")}
              <span className="field-with-action">
                <input
                  autoComplete="new-password"
                  type="text"
                  value={userForm.password}
                  onChange={(event) => onUserFormChange({ ...userForm, password: event.target.value })}
                />
                <button
                  type="button"
                  onClick={() => onUserFormChange({ ...userForm, password: generateTemporaryPassword() })}
                >
                  {t("departmentsGeneratePassword")}
                </button>
              </span>
            </label>
          </>
        )}
        {userCreateTab === "access" && (
          <>
            <label>
              {t("departmentsNewUserRole")}
              <select
                value={userForm.roleId}
                onChange={(event) => onUserFormChange({ ...userForm, roleId: event.target.value })}
              >
                <option value="">{t("departmentsNoRoleSelected")}</option>
                {roles.map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              {t("departmentsNewUserCostCenter")}
              <select
                value={userForm.costCenterId}
                onChange={(event) => onUserFormChange({ ...userForm, costCenterId: event.target.value })}
              >
                <option value="">{t("departmentsNoCostCenterSelected")}</option>
                {selectableCostCenters.map((costCenter) => (
                  <option key={costCenter.id} value={costCenter.id}>
                    {costCenter.code} - {costCenter.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="inline-note org-user-access-note">{t("departmentsUserAccessNote")}</div>
          </>
        )}
        <div className="provider-actions org-actions">
          <Button onClick={onCreateUser} disabled={saving || !userForm.email.trim() || userForm.password.length < 8}>
            {t("departmentsAddUser")}
          </Button>
        </div>
      </div>
    </div>
  );
}

function generateTemporaryPassword() {
  const alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%";
  const bytes = new Uint8Array(14);
  window.crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => alphabet[byte % alphabet.length]).join("");
}
