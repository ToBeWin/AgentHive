import { ShieldCheck } from "lucide-react";
import { useLocale } from "../../i18n-context";
import type { AuthUser } from "../../lib/api";

interface RoleCurrentPanelProps {
  effectiveUser: AuthUser;
  grantedPermissionCount: string;
  lockedModuleCount: number;
  roleLabel: string;
  visibleModuleCount: number;
}

export function RoleCurrentPanel({
  effectiveUser,
  grantedPermissionCount,
  lockedModuleCount,
  roleLabel,
  visibleModuleCount,
}: RoleCurrentPanelProps) {
  const { t } = useLocale();

  return (
    <div className="settings-role-current">
      <div className="settings-role-identity">
        <ShieldCheck size={22} />
        <div>
          <span>{t("settingsCurrentRole")}</span>
          <strong>{roleLabel}</strong>
          <p>{effectiveUser.full_name ?? effectiveUser.email}</p>
        </div>
      </div>
      <div className="settings-role-metrics">
        <article>
          <span>{t("settingsAccessibleModules")}</span>
          <strong>{visibleModuleCount}</strong>
        </article>
        <article>
          <span>{t("settingsLockedModules")}</span>
          <strong>{lockedModuleCount}</strong>
        </article>
        <article>
          <span>{t("settingsGrantedPermissions")}</span>
          <strong>{grantedPermissionCount}</strong>
        </article>
      </div>
    </div>
  );
}
