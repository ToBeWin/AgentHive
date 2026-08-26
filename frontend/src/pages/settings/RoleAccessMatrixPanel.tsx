import { CheckCircle2, LockKeyhole } from "lucide-react";
import { cx } from "../../components/app-ui";
import { navItems } from "../../data";
import { useLocale } from "../../i18n-context";
import type { AuthUser } from "../../lib/api";
import { canAccessRequirement } from "../../lib/permissions";

export function RoleAccessMatrixPanel({ accessUser }: { accessUser: AuthUser | null }) {
  const { t } = useLocale();

  return (
    <div className="settings-role-access">
      <div>
        <strong>{t("settingsRoleAccessMatrix")}</strong>
        <p>{t("settingsRoleAccessMatrixHelp")}</p>
      </div>
      <div className="settings-role-access-list">
        {navItems.map((item) => {
          const Icon = item.icon;
          const allowed = canAccessRequirement(accessUser, item);
          return (
            <span className={cx("settings-role-access-item", allowed && "allowed")} key={item.id}>
              {allowed ? <CheckCircle2 size={15} /> : <LockKeyhole size={15} />}
              <Icon size={15} />
              {t(item.id)}
            </span>
          );
        })}
      </div>
    </div>
  );
}
