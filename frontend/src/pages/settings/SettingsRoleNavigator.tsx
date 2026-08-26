import { ClipboardCheck, FileArchive, ShieldCheck, Wrench } from "lucide-react";
import type { ReactNode } from "react";
import { Button, cx, StatusBadge } from "../../components/app-ui";
import type { SystemDiagnostics } from "../../hooks/admin/system";
import { useLocale } from "../../i18n-context";
import { deliveryStatusLabel, deliveryTone, healthRows } from "./settingsUtils";
import type { SettingsPageTab } from "./settingsWorkspaceTypes";

type NavigatorTone = "good" | "warning" | "bad";

interface NavigatorItem {
  action: string;
  detail: string;
  icon: ReactNode;
  id: SettingsPageTab;
  owner: string;
  status: string;
  title: string;
  tone: NavigatorTone;
}

interface SettingsRoleNavigatorProps {
  activeTab: SettingsPageTab;
  diagnostics: SystemDiagnostics | null;
  onOpenTab: (tab: SettingsPageTab) => void;
}

export function SettingsRoleNavigator({ activeTab, diagnostics, onOpenTab }: SettingsRoleNavigatorProps) {
  const { t } = useLocale();
  const readiness = diagnostics?.readiness ?? null;
  const delivery = readiness?.delivery ?? null;
  const componentRows = healthRows(readiness);
  const unhealthyCount = componentRows.filter(
    (row) => row.report.status === "unhealthy" || row.report.status === "error",
  ).length;
  const degradedCount = componentRows.filter(
    (row) => row.report.status === "degraded" || row.report.status === "not_configured",
  ).length;
  const deliveryToneValue: NavigatorTone = delivery ? deliveryTone(delivery.status) : "warning";
  const deliveryStatus = delivery ? deliveryStatusLabel(delivery.status, t) : t("settingsNavigatorUnknown");
  const diagnosticsStatus =
    unhealthyCount > 0
      ? t("settingsNavigatorBlocked")
      : degradedCount > 0
        ? t("settingsNavigatorReview")
        : t("settingsNavigatorReady");

  const items: NavigatorItem[] = [
    {
      id: "delivery" as const,
      action: t("settingsNavigatorDeliveryAction"),
      detail: delivery
        ? t("settingsNavigatorDeliveryDetail")
            .replace("{{blockers}}", String(delivery.blocker_count))
            .replace("{{warnings}}", String(delivery.warning_count))
        : t("settingsNavigatorDeliveryEmpty"),
      icon: <ClipboardCheck size={18} />,
      owner: t("settingsNavigatorDeliveryOwner"),
      status: deliveryStatus,
      title: t("settingsNavigatorDeliveryTitle"),
      tone: deliveryToneValue,
    },
    {
      id: "roles" as const,
      action: t("settingsNavigatorRolesAction"),
      detail: t("settingsNavigatorRolesDetail"),
      icon: <ShieldCheck size={18} />,
      owner: t("settingsNavigatorRolesOwner"),
      status: t("settingsNavigatorGoverned"),
      title: t("settingsNavigatorRolesTitle"),
      tone: "good" satisfies NavigatorTone,
    },
    {
      id: "diagnostics" as const,
      action: t("settingsNavigatorDiagnosticsAction"),
      detail: t("settingsNavigatorDiagnosticsDetail")
        .replace("{{unhealthy}}", String(unhealthyCount))
        .replace("{{degraded}}", String(degradedCount)),
      icon: <Wrench size={18} />,
      owner: t("settingsNavigatorDiagnosticsOwner"),
      status: diagnosticsStatus,
      title: t("settingsNavigatorDiagnosticsTitle"),
      tone: unhealthyCount > 0 ? "bad" : degradedCount > 0 ? "warning" : "good",
    },
    {
      id: "exports" as const,
      action: t("settingsNavigatorExportsAction"),
      detail: t("settingsNavigatorExportsDetail"),
      icon: <FileArchive size={18} />,
      owner: t("settingsNavigatorExportsOwner"),
      status: t("settingsNavigatorEvidence"),
      title: t("settingsNavigatorExportsTitle"),
      tone: "good" satisfies NavigatorTone,
    },
  ];

  return (
    <section className="settings-role-navigator" aria-label={t("settingsNavigatorTitle")}>
      <div className="settings-role-navigator-head">
        <div>
          <span>{t("settingsNavigatorEyebrow")}</span>
          <strong>{t("settingsNavigatorTitle")}</strong>
        </div>
        <p>{t("settingsNavigatorHelp")}</p>
      </div>
      <div className="settings-role-navigator-grid">
        {items.map((item) => (
          <NavigatorCard
            active={activeTab === item.id}
            action={item.action}
            detail={item.detail}
            icon={item.icon}
            key={item.id}
            onOpen={() => onOpenTab(item.id)}
            owner={item.owner}
            status={item.status}
            title={item.title}
            tone={item.tone}
          />
        ))}
      </div>
    </section>
  );
}

function NavigatorCard({
  action,
  active,
  detail,
  icon,
  onOpen,
  owner,
  status,
  title,
  tone,
}: {
  action: string;
  active: boolean;
  detail: string;
  icon: ReactNode;
  onOpen: () => void;
  owner: string;
  status: string;
  title: string;
  tone: NavigatorTone;
}) {
  return (
    <article className={cx("settings-role-navigator-card", active && "active", tone)}>
      <div className="settings-role-navigator-card-head">
        <span className="settings-role-navigator-icon">{icon}</span>
        <StatusBadge status={status} />
      </div>
      <strong>{title}</strong>
      <p>{detail}</p>
      <div className="settings-role-navigator-foot">
        <small>{owner}</small>
        <Button onClick={onOpen} variant={active ? "ghost" : "secondary"}>
          {action}
        </Button>
      </div>
    </article>
  );
}
