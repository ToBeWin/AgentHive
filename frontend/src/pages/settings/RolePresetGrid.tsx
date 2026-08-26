import { BadgeCheck, LockKeyhole } from "lucide-react";
import { cx } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { AuthUser } from "../../lib/api";
import { rolePresets } from "./roleWorkspaceData";

export function RolePresetGrid({ effectiveUser }: { effectiveUser: AuthUser }) {
  const { t } = useLocale();

  return (
    <div className="settings-role-grid">
      {rolePresets.map((role) => {
        const Icon = role.icon;
        const covered = role.permissions.filter(
          (permission) => effectiveUser.is_tenant_admin || effectiveUser.permissions.includes(permission),
        ).length;
        const isFullyCovered = covered === role.permissions.length;
        return (
          <article className={cx("settings-role-card", isFullyCovered && "settings-role-card-active")} key={role.key}>
            <div className="settings-role-card-head">
              <Icon size={19} />
              <div>
                <strong>{t(role.titleKey)}</strong>
                <span>{t(role.scopeKey)}</span>
              </div>
              {isFullyCovered ? <BadgeCheck size={18} /> : <LockKeyhole size={18} />}
            </div>
            <p>{t(role.descriptionKey)}</p>
            <div className="settings-role-permissions">
              {role.permissions.map((permission) => {
                const granted = effectiveUser.is_tenant_admin || effectiveUser.permissions.includes(permission);
                return (
                  <code className={cx(granted && "granted")} key={permission}>
                    {permission}
                  </code>
                );
              })}
            </div>
          </article>
        );
      })}
    </div>
  );
}
