import { useState } from "react";
import { PageTabs, Panel } from "../../components/app-ui";
import { navItems } from "../../data";
import { useLocale } from "../../i18n-context";
import type { AuthUser } from "../../lib/api";
import { canAccessRequirement } from "../../lib/permissions";
import { RoleAccessMatrixPanel } from "./RoleAccessMatrixPanel";
import { RoleCurrentPanel } from "./RoleCurrentPanel";
import { RolePresetGrid } from "./RolePresetGrid";
import { governancePermissions, inferRoleLabel } from "./roleWorkspaceData";

type RoleWorkspaceTab = "current" | "presets" | "matrix";

export function RoleWorkspacePanel({ isPrototype, user }: { isPrototype: boolean; user: AuthUser | null }) {
  const { t } = useLocale();
  const [activeTab, setActiveTab] = useState<RoleWorkspaceTab>("current");
  const effectiveUser = user ?? {
    email: "prototype@agenthive.local",
    full_name: "Prototype Admin",
    id: "prototype",
    is_super_admin: false,
    is_tenant_admin: true,
    permissions: ["tenant.admin"],
    tenant_id: "prototype",
  };
  const accessUser = isPrototype ? effectiveUser : user;
  const visibleNav = navItems.filter((item) => canAccessRequirement(accessUser, item));
  const lockedNav = navItems.filter((item) => !canAccessRequirement(accessUser, item));
  const grantedPermissions = effectiveUser.is_tenant_admin
    ? governancePermissions
    : governancePermissions.filter((permission) => effectiveUser.permissions.includes(permission));
  const roleLabel = effectiveUser.is_tenant_admin
    ? t("settingsRoleEnterpriseAdmin")
    : inferRoleLabel(effectiveUser.permissions, t);

  return (
    <Panel
      title={t("settingsRoleWorkspace")}
      subtitle={t("settingsRoleWorkspaceHelp")}
      actions={<span className="settings-role-mode">{t("settingsRoleUnifiedConsole")}</span>}
      className="settings-role-workspace"
    >
      <PageTabs
        active={activeTab}
        onChange={setActiveTab}
        tabs={[
          { id: "current", label: t("settingsRoleTabCurrent"), description: t("settingsRoleTabCurrentDesc") },
          { id: "presets", label: t("settingsRoleTabPresets"), description: t("settingsRoleTabPresetsDesc") },
          { id: "matrix", label: t("settingsRoleTabMatrix"), description: t("settingsRoleTabMatrixDesc") },
        ]}
      />

      {activeTab === "current" && (
        <RoleCurrentPanel
          effectiveUser={effectiveUser}
          grantedPermissionCount={
            effectiveUser.is_tenant_admin ? t("settingsRoleAll") : String(grantedPermissions.length)
          }
          lockedModuleCount={lockedNav.length}
          roleLabel={roleLabel}
          visibleModuleCount={visibleNav.length}
        />
      )}

      {activeTab === "presets" && <RolePresetGrid effectiveUser={effectiveUser} />}

      {activeTab === "matrix" && <RoleAccessMatrixPanel accessUser={accessUser} />}
    </Panel>
  );
}
