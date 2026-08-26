import { AlertTriangle, CheckCircle2, CircleDashed } from "lucide-react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { DeliveryAssessment, DeliveryCheck } from "../../lib/api";
import {
  deliveryIssueRows,
  deliveryStatusLabel,
  deliveryTone,
  localizedDeliverySummary,
  localizedRemediationParts,
} from "./settingsUtils";

export function DeliveryReadinessPanel({ delivery }: { delivery: DeliveryAssessment | null | undefined }) {
  const { t } = useLocale();
  const tone = deliveryTone(delivery?.status);
  const issues = delivery ? deliveryIssueRows([...delivery.blockers, ...delivery.warnings]).slice(0, 5) : [];
  const Icon = tone === "good" ? CheckCircle2 : tone === "warning" ? CircleDashed : AlertTriangle;

  return (
    <section className="panel settings-delivery-panel">
      <div className="panel-title">
        <h2>{t("settingsDeliveryReadiness")}</h2>
        {delivery && <StatusBadge status={delivery.status} label={deliveryStatusLabel(delivery.status, t)} />}
      </div>
      <div className={cx("settings-delivery-hero", `settings-delivery-${tone}`)}>
        <Icon size={24} />
        <div>
          <strong>{delivery ? deliveryStatusLabel(delivery.status, t) : t("settingsDeliveryUnavailable")}</strong>
          <p>{localizedDeliverySummary(delivery, t, t("settingsDeliveryUnavailableDetail"))}</p>
        </div>
      </div>
      <div className="settings-delivery-counts">
        <span>
          <strong>{delivery?.blocker_count ?? "-"}</strong>
          {t("settingsDeliveryBlockers")}
        </span>
        <span>
          <strong>{delivery?.warning_count ?? "-"}</strong>
          {t("settingsDeliveryWarnings")}
        </span>
        <span>
          <strong>{delivery?.checks.length ?? "-"}</strong>
          {t("settingsDeliveryChecks")}
        </span>
      </div>
      {issues.length ? (
        <div className="settings-delivery-issues">
          {issues.map((issue) => (
            <DeliveryIssueCard issue={issue} key={`${issue.severity}-${issue.id}`} />
          ))}
        </div>
      ) : (
        <p className="muted">{delivery ? t("settingsDeliveryNoIssues") : t("settingsLoadingDiagnostics")}</p>
      )}
    </section>
  );
}

function DeliveryIssueCard({ issue }: { issue: DeliveryCheck }) {
  const { t } = useLocale();
  const remediation = localizedRemediationParts(issue.remediation, t);

  return (
    <article className="settings-delivery-issue">
      <div className="settings-delivery-issue-head">
        <div>
          <strong>{issue.label || issue.id}</strong>
          <span>{issue.message || issue.component}</span>
        </div>
        <StatusBadge
          status={issue.severity === "warning" ? "degraded" : issue.severity}
          label={severityLabel(issue.severity, t)}
        />
      </div>
      {remediation && (
        <div className="settings-delivery-remediation">
          {remediation.summary && (
            <p>
              <b>{t("settingsRemediationSummary")}</b>
              {remediation.summary}
            </p>
          )}
          {remediation.action && (
            <p>
              <b>{t("settingsRemediationAction")}</b>
              {remediation.action}
            </p>
          )}
          {remediation.docsAnchor && (
            <span className="settings-delivery-doc-anchor">
              {t("settingsRemediationDocsAnchor")} <code>{remediation.docsAnchor}</code>
            </span>
          )}
        </div>
      )}
    </article>
  );
}

function severityLabel(severity: string, t: (key: string) => string) {
  if (severity === "blocker") {
    return t("settingsDeliverySeverityBlocker");
  }
  if (severity === "warning") {
    return t("settingsDeliverySeverityWarning");
  }
  return severity;
}
