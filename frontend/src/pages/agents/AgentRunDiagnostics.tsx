import { useLocale } from "../../i18n-context";
import type { AgentRunResponse } from "../../lib/api";

export function AgentRunDiagnostics({ response }: { response: AgentRunResponse }) {
  const { t } = useLocale();
  const metadata = response.metadata;
  const knowledge = typeof metadata.knowledge === "object" && metadata.knowledge !== null ? metadata.knowledge : null;
  const agentInstance =
    typeof metadata.agent_instance === "object" && metadata.agent_instance !== null
      ? (metadata.agent_instance as Record<string, unknown>)
      : null;
  const mediaJob =
    typeof metadata.media_generation_job === "object" && metadata.media_generation_job !== null
      ? (metadata.media_generation_job as Record<string, unknown>)
      : null;
  const sourceCount = knowledge ? String((knowledge as Record<string, unknown>).source_count ?? 0) : "0";
  const instanceEnabled = agentInstance?.enabled === true;

  return (
    <div className="agent-governance-grid">
      <div>
        <span>{t("agentsRuntimeInstance")}</span>
        <strong>
          {instanceEnabled ? String(agentInstance?.name ?? agentInstance?.slug ?? "-") : t("agentsPolicyDefault")}
        </strong>
        <small>
          {instanceEnabled
            ? visibilityLabel(String(agentInstance?.visibility ?? ""), t) || t("agentsNoDiagnostic")
            : t("agentsNoDiagnostic")}
        </small>
      </div>
      <div>
        <span>{t("agentsGateway")}</span>
        <strong>{response.model_key}</strong>
        <small>{response.request_id}</small>
      </div>
      <div>
        <span>{t("agentsLicenseGate")}</span>
        <strong>{String(metadata.license_gate ?? t("agentsNoDiagnostic"))}</strong>
        <small>{String(metadata.license_gate_reason ?? metadata.required_module ?? t("agentsNoDiagnostic"))}</small>
      </div>
      <div>
        <span>{t("agentsKnowledge")}</span>
        <strong>{t("agentsSourcesCount").replace("{{count}}", sourceCount)}</strong>
        <small>
          {knowledge
            ? String((knowledge as Record<string, unknown>).reason ?? t("agentsRetrievalChecked"))
            : t("agentsNotChecked")}
        </small>
      </div>
      {mediaJob && (
        <div>
          <span>{t("agentsMediaJob")}</span>
          <strong>{String(mediaJob.status ?? "-")}</strong>
          <small>
            {t("agentsMediaJobRoute")
              .replace("{{id}}", String(mediaJob.id ?? "-"))
              .replace("{{kind}}", String(mediaJob.kind ?? "-"))
              .replace("{{model}}", String(mediaJob.model_key ?? "-"))}
          </small>
        </div>
      )}
    </div>
  );
}

function visibilityLabel(visibility: string, t: (key: string) => string) {
  if (visibility === "tenant") {
    return t("agentInstancesTenantWide");
  }
  if (visibility === "department") {
    return t("agentInstancesDepartmentScoped");
  }
  if (visibility === "private") {
    return t("agentInstancesPrivate");
  }
  return "";
}
