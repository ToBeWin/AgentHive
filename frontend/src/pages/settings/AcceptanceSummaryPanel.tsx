import { StatusBadge } from "../../components/app-ui";
import type { SystemDiagnostics } from "../../hooks/admin/system";
import { useLocale } from "../../i18n-context";
import { deliveryStatusLabel, healthRows } from "./settingsUtils";

export function AcceptanceSummaryPanel({ diagnostics }: { diagnostics: SystemDiagnostics | null }) {
  const { t } = useLocale();
  const readiness = diagnostics?.readiness ?? null;
  const delivery = readiness?.delivery ?? null;
  const connectionAcceptance = diagnostics?.connection_acceptance ?? null;
  const knowledgeAcceptance = diagnostics?.knowledge_acceptance ?? null;
  const components = healthRows(readiness);

  return (
    <div className="settings-acceptance-summary">
      <article>
        <span>{t("settingsAcceptanceStatus")}</span>
        <strong>{delivery ? deliveryStatusLabel(delivery.status, t) : t("settingsDeliveryUnavailable")}</strong>
        {delivery && <StatusBadge status={delivery.status} label={deliveryStatusLabel(delivery.status, t)} />}
      </article>
      <article>
        <span>{t("settingsAcceptanceEvidence")}</span>
        <strong>{components.length}</strong>
        <p>{t("settingsAcceptanceEvidenceDetail")}</p>
      </article>
      <article>
        <span>{t("settingsAcceptanceConnectionEvidence")}</span>
        <strong>{connectionAcceptance?.live_network_call_count ?? "-"}</strong>
        <p>
          {connectionAcceptance
            ? t("settingsAcceptanceConnectionEvidenceDetail")
                .replace("{{media}}", String(connectionAcceptance.media_live_probe_count))
                .replace("{{failed}}", String(connectionAcceptance.failed_recent_count))
            : t("settingsAcceptanceConnectionEvidenceUnavailable")}
        </p>
      </article>
      <article>
        <span>{t("settingsAcceptanceKnowledgeEvidence")}</span>
        <strong>{knowledgeAcceptance?.runs_with_sources_count ?? "-"}</strong>
        <p>
          {knowledgeAcceptance
            ? t("settingsAcceptanceKnowledgeEvidenceDetail")
                .replace("{{runs}}", String(knowledgeAcceptance.knowledge_enabled_run_count))
                .replace("{{review}}", String(knowledgeAcceptance.human_review_required_count))
            : t("settingsAcceptanceKnowledgeEvidenceUnavailable")}
        </p>
      </article>
    </div>
  );
}
