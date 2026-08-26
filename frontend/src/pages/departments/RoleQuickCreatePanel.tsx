import { useMemo, useState } from "react";
import { Button, cx, PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { PermissionCatalogItem, RolePresetItem } from "../../lib/api";
import {
  getPermissionCategoryLabelKey,
  groupPermissionCatalog,
  parsePermissionInput,
  type RoleFormState,
  togglePermissionValue,
} from "./departmentUtils";
import type { RoleCreateTab } from "./orgSetupTypes";

interface RoleQuickCreatePanelProps {
  onCreateRole: () => void;
  onRoleFormChange: (form: RoleFormState) => void;
  roleForm: RoleFormState;
  rolePermissions: PermissionCatalogItem[];
  rolePermissionsLoading: boolean;
  rolePresets: RolePresetItem[];
  rolePresetsLoading: boolean;
  saving: boolean;
}

export function RoleQuickCreatePanel({
  onCreateRole,
  onRoleFormChange,
  roleForm,
  rolePermissions,
  rolePermissionsLoading,
  rolePresets,
  rolePresetsLoading,
  saving,
}: RoleQuickCreatePanelProps) {
  const { t } = useLocale();
  const [roleCreateTab, setRoleCreateTab] = useState<RoleCreateTab>("basic");
  const groupedPermissions = useMemo(() => groupPermissionCatalog(rolePermissions), [rolePermissions]);
  const selectedPermissions = useMemo(
    () => new Set(parsePermissionInput(roleForm.permissions)),
    [roleForm.permissions],
  );
  const toggleRolePermission = (permission: string) => {
    onRoleFormChange({
      ...roleForm,
      permissions: togglePermissionValue(roleForm.permissions, permission),
      templateKey: "",
    });
  };
  const applyRolePreset = (presetKey: string) => {
    const preset = rolePresets.find((item) => item.key === presetKey);
    if (!preset) {
      onRoleFormChange({ ...roleForm, templateKey: "" });
      return;
    }
    onRoleFormChange({
      description: preset.description,
      name: preset.name,
      permissions: preset.permissions.join(","),
      templateKey: preset.key,
    });
  };

  return (
    <div className="org-role-create">
      <PageTabs
        active={roleCreateTab}
        onChange={setRoleCreateTab}
        tabs={[
          {
            id: "basic",
            label: t("departmentsRoleBasicTab"),
            description: t("departmentsRoleBasicTabDesc"),
          },
          {
            id: "permissions",
            label: t("departmentsRolePermissionsTab"),
            description: t("departmentsRolePermissionsTabDesc"),
          },
        ]}
      />
      <div className="org-admin-grid">
        {roleCreateTab === "basic" && (
          <>
            <label>
              {t("departmentsRoleTemplate")}
              <select
                disabled={rolePresetsLoading}
                value={roleForm.templateKey}
                onChange={(event) => applyRolePreset(event.target.value)}
              >
                <option value="">
                  {rolePresetsLoading ? t("departmentsLoadingRoleTemplates") : t("departmentsNoRoleTemplate")}
                </option>
                {rolePresets.map((preset) => (
                  <option key={preset.key} value={preset.key}>
                    {preset.name} · {preset.scope}
                  </option>
                ))}
              </select>
            </label>
            <label>
              {t("departmentsRole")}
              <input
                value={roleForm.name}
                onChange={(event) => onRoleFormChange({ ...roleForm, name: event.target.value, templateKey: "" })}
              />
            </label>
            <label>
              {t("departmentsRoleDescription")}
              <input
                value={roleForm.description}
                onChange={(event) =>
                  onRoleFormChange({ ...roleForm, description: event.target.value, templateKey: "" })
                }
              />
            </label>
          </>
        )}
        {roleCreateTab === "permissions" && (
          <RolePermissionSelector
            groupedPermissions={groupedPermissions}
            loading={rolePermissionsLoading}
            onPermissionsChange={(permissions) => onRoleFormChange({ ...roleForm, permissions, templateKey: "" })}
            onTogglePermission={toggleRolePermission}
            permissions={roleForm.permissions}
            selectedPermissions={selectedPermissions}
          />
        )}
        <div className="provider-actions org-actions">
          <Button onClick={onCreateRole} disabled={saving || !roleForm.name.trim()}>
            {t("departmentsAddRole")}
          </Button>
        </div>
      </div>
    </div>
  );
}

function RolePermissionSelector({
  groupedPermissions,
  loading,
  onPermissionsChange,
  onTogglePermission,
  permissions,
  selectedPermissions,
}: {
  groupedPermissions: ReturnType<typeof groupPermissionCatalog>;
  loading: boolean;
  onPermissionsChange: (permissions: string) => void;
  onTogglePermission: (permission: string) => void;
  permissions: string;
  selectedPermissions: Set<string>;
}) {
  const { t } = useLocale();

  return (
    <div className="form-field permission-field wide">
      <label htmlFor="role-permissions-input">{t("departmentsPermissions")}</label>
      <input
        id="role-permissions-input"
        placeholder={t("departmentsPermissionsPlaceholder")}
        value={permissions}
        onChange={(event) => onPermissionsChange(event.target.value)}
      />
      <fieldset className="permission-catalog">
        <legend>{t("departmentsPermissionCatalog")}</legend>
        {loading ? (
          <small>{t("departmentsLoadingPermissions")}</small>
        ) : (
          groupedPermissions.map((group) => (
            <div className="permission-group" key={group.category}>
              <div className="permission-group-header">
                <span>{t(getPermissionCategoryLabelKey(group.category))}</span>
                <small>{t("departmentsPermissionsCount").replace("{{count}}", String(group.items.length))}</small>
              </div>
              <div className="permission-buttons">
                {group.items.map((permission) => {
                  const selected = selectedPermissions.has(permission.value);
                  return (
                    <button
                      aria-pressed={selected}
                      className={cx(selected ? "active" : false)}
                      key={permission.value}
                      title={`${permission.label} (${permission.value})`}
                      type="button"
                      onClick={() => onTogglePermission(permission.value)}
                    >
                      {permission.value}
                    </button>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </fieldset>
    </div>
  );
}
