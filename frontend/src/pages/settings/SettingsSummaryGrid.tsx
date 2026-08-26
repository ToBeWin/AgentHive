import { Activity, Server, ShieldAlert, Wrench } from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "../../components/app-ui";
import type { SystemDiagnostics } from "../../hooks/admin/system";
import type { Locale } from "../../i18n";
import { deliveryStatusLabel, deliveryTone, formatCheckedAt, healthRows, statusTone } from "./settingsUtils";

export function SettingsSummaryGrid({
  diagnostics,
  locale,
  t,
}: {
  diagnostics: SystemDiagnostics | null;
  locale: Locale;
  t: (key: string) => string;
}) {
  const readiness = diagnostics?.readiness ?? null;
  const health = diagnostics?.health ?? null;
  const info = diagnostics?.info ?? null;
  const components = healthRows(readiness);
  const delivery = readiness?.delivery ?? null;
  const unhealthyCount = components.filter(
    (row) => row.report.status === "unhealthy" || row.report.status === "error",
  ).length;
  const degradedCount = components.filter(
    (row) => row.report.status === "degraded" || row.report.status === "not_configured",
  ).length;

  return (
    <div className="kpi-grid settings-summary-grid">
      <SummaryCard
        icon={<Activity size={20} />}
        label={t("settingsReadiness")}
        value={delivery ? deliveryStatusLabel(delivery.status, t) : (readiness?.status ?? "-")}
        tone={delivery ? deliveryTone(delivery.status) : statusTone(readiness?.status ?? "unhealthy")}
        detail={
          delivery
            ? t("settingsDeliverySummaryDetail")
                .replace("{{blockers}}", String(delivery.blocker_count))
                .replace("{{warnings}}", String(delivery.warning_count))
            : readiness
              ? formatCheckedAt(readiness.checked_at, locale)
              : t("settingsLoadingDiagnostics")
        }
      />
      <SummaryCard
        icon={<Server size={20} />}
        label={t("settingsBackend")}
        value={info?.version ?? health?.version ?? "-"}
        tone="good"
        detail={health ? `${health.service} · ${health.environment}` : t("settingsLoadingDiagnostics")}
      />
      <SummaryCard
        icon={<ShieldAlert size={20} />}
        label={t("settingsAttentionItems")}
        value={`${unhealthyCount + degradedCount}`}
        tone={unhealthyCount > 0 ? "bad" : degradedCount > 0 ? "warning" : "good"}
        detail={t("settingsAttentionDetail")
          .replace("{{unhealthy}}", String(unhealthyCount))
          .replace("{{degraded}}", String(degradedCount))}
      />
      <SummaryCard
        icon={<Wrench size={20} />}
        label={t("settingsComponents")}
        value={`${components.length}`}
        tone="good"
        detail={t("settingsComponentsDetail")}
      />
    </div>
  );
}

function SummaryCard({
  detail,
  icon,
  label,
  tone,
  value,
}: {
  detail: string;
  icon: ReactNode;
  label: string;
  tone: "good" | "warning" | "bad";
  value: string;
}) {
  return (
    <article className="metric-card settings-summary-card">
      <div className="metric-label">
        <span>{label}</span>
        {icon}
      </div>
      <strong className={cx(tone === "bad" ? "bad" : tone === "warning" ? "warning-text" : "good")}>{value}</strong>
      <p>{detail}</p>
    </article>
  );
}
