import { useMemo, useState } from "react";
import { PageTabs, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { SystemHealthReport } from "../../lib/api";
import type { ComponentHealthRow } from "./settingsUtils";
import {
  componentLabel,
  componentStatusLabel,
  detailPairs,
  formatCheckedAt,
  healthRows,
  localizedRemediationText,
} from "./settingsUtils";

type ComponentTableTab = "all" | "blocked" | "attention" | "healthy";

export function SystemComponentTable({ report }: { report: SystemHealthReport | null }) {
  const { locale, t } = useLocale();
  const [activeTab, setActiveTab] = useState<ComponentTableTab>("all");
  const rows = healthRows(report);
  const rowGroups = useMemo(
    () => ({
      all: rows,
      attention: rows.filter((row) => row.report.status === "degraded" || row.report.status === "not_configured"),
      blocked: rows.filter((row) => row.report.status === "unhealthy" || row.report.status === "error"),
      healthy: rows.filter((row) => row.report.status === "healthy" || row.report.status === "configured"),
    }),
    [rows],
  );
  const visibleRows = rowGroups[activeTab];

  return (
    <section className="panel">
      <div className="panel-title">
        <h2>{t("settingsComponentHealth")}</h2>
        {report && (
          <span className="row-subtitle">
            {t("settingsCheckedAt").replace("{{time}}", formatCheckedAt(report.checked_at, locale))}
          </span>
        )}
      </div>
      <PageTabs
        active={activeTab}
        onChange={setActiveTab}
        tabs={[
          {
            id: "all",
            label: t("settingsComponentTabAll").replace("{{count}}", String(rowGroups.all.length)),
            description: t("settingsComponentTabAllDesc"),
          },
          {
            id: "blocked",
            label: t("settingsComponentTabBlocked").replace("{{count}}", String(rowGroups.blocked.length)),
            description: t("settingsComponentTabBlockedDesc"),
          },
          {
            id: "attention",
            label: t("settingsComponentTabAttention").replace("{{count}}", String(rowGroups.attention.length)),
            description: t("settingsComponentTabAttentionDesc"),
          },
          {
            id: "healthy",
            label: t("settingsComponentTabHealthy").replace("{{count}}", String(rowGroups.healthy.length)),
            description: t("settingsComponentTabHealthyDesc"),
          },
        ]}
      />
      <table className="data-table settings-component-table">
        <thead>
          <tr>
            <th>{t("settingsComponent")}</th>
            <th>{t("settingsStatus")}</th>
            <th>{t("settingsMessage")}</th>
            <th>{t("settingsKeyDetails")}</th>
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((row) => {
            const pairs = visibleDetailPairs(row, t).slice(0, 4);
            const remediation = localizedRemediationText(row.report.remediation, t);
            return (
              <tr key={row.key}>
                <td>
                  <strong>{componentLabel(row.key, t)}</strong>
                  {row.report.component && (
                    <span className="row-subtitle">{componentLabel(row.report.component, t)}</span>
                  )}
                </td>
                <td>
                  <StatusBadge status={row.report.status} label={componentStatusLabel(row.report.status, t)} />
                </td>
                <td>
                  <div className="settings-component-message">
                    <span>{row.report.message ?? "-"}</span>
                    {remediation && (
                      <span className="settings-remediation">
                        <strong>{t("settingsRemediation")}</strong>
                        {remediation}
                      </span>
                    )}
                  </div>
                </td>
                <td>
                  {pairs.length ? (
                    <div className="settings-detail-pairs">
                      {pairs.map((pair) => (
                        <span key={pair.key}>
                          {pair.key}: <code>{pair.value}</code>
                        </span>
                      ))}
                    </div>
                  ) : (
                    "-"
                  )}
                </td>
              </tr>
            );
          })}
          {visibleRows.length === 0 && (
            <tr>
              <td colSpan={4}>{t("settingsNoComponentData")}</td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}

function visibleDetailPairs(row: ComponentHealthRow, t: (key: string) => string) {
  return detailPairs(row.report.details, t).sort(
    (left, right) => detailPriority(left.rawKey) - detailPriority(right.rawKey),
  );
}

function detailPriority(key: string) {
  const normalized = key.toLowerCase();
  if (normalized.includes("missing")) {
    return 0;
  }
  if (normalized.includes("webhook")) {
    return 1;
  }
  if (normalized.includes("configured")) {
    return 2;
  }
  return 3;
}
