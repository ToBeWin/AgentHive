import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { SystemComponentReport } from "../../lib/api";
import { componentStatusLabel, formatDetailValue } from "./settingsUtils";

export function ProductionConfigPanel({ report }: { report: SystemComponentReport | null }) {
  const { t } = useLocale();
  const issues = report?.details?.issues;
  const issueList = Array.isArray(issues) ? issues.map(formatDetailValue) : [];
  const Icon = report?.status === "healthy" ? CheckCircle2 : AlertTriangle;

  return (
    <section className="panel">
      <div className="panel-title">
        <h2>{t("settingsProductionConfig")}</h2>
        {report && <StatusBadge status={report.status} label={componentStatusLabel(report.status, t)} />}
      </div>
      <div className="settings-config-summary">
        <Icon size={22} />
        <div>
          <strong>{report?.message ?? t("settingsProductionConfigUnavailable")}</strong>
          <p>{t("settingsProductionConfigHint")}</p>
        </div>
      </div>
      {issueList.length > 0 && (
        <ul className="settings-issue-list">
          {issueList.map((issue) => (
            <li key={issue}>{issue}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
