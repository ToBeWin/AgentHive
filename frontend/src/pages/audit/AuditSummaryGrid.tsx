import { useLocale } from "../../i18n-context";
import type { AuditLogItem } from "../../lib/api";
import { formatNumber } from "../../lib/formatters";
import { auditSummary } from "./auditUtils";

export function AuditSummaryGrid({ rows, total }: { rows: AuditLogItem[]; total: number }) {
  const { locale, t } = useLocale();
  const summary = auditSummary(rows);

  return (
    <div className="audit-summary-grid">
      <AuditMetric
        label={t("auditEvents")}
        value={formatNumber(rows.length, {}, locale)}
        detail={t("auditTotal").replace("{{count}}", String(total))}
      />
      <AuditMetric
        label={t("auditFailures")}
        value={formatNumber(summary.failures, {}, locale)}
        detail={t("auditRequiresReview")}
      />
      <AuditMetric
        label={t("auditActors")}
        value={formatNumber(summary.actorCount, {}, locale)}
        detail={t("auditUniqueActors")}
      />
      <AuditMetric
        label={t("auditSystems")}
        value={formatNumber(summary.systemEvents, {}, locale)}
        detail={t("auditSystemEvents")}
      />
    </div>
  );
}

function AuditMetric({ detail, label, value }: { detail: string; label: string; value: string }) {
  return (
    <section className="panel audit-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </section>
  );
}
