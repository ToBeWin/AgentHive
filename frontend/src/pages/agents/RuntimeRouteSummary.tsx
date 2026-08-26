import { useLocale } from "../../i18n-context";
import { agentDisplayName } from "../../lib/agentDisplay";
import type { AgentInstanceResponse } from "../../lib/api";
import { readinessReasonLabels } from "../../lib/readiness";

export function RuntimeRouteSummary({ instance }: { instance: AgentInstanceResponse | null }) {
  const { locale, t } = useLocale();

  if (!instance) {
    return (
      <div className="agent-runtime-summary">
        <span>{t("agentsPolicyRoute")}</span>
        <strong>default-chat</strong>
        <small>{t("agentsPolicyRouteHelp")}</small>
      </div>
    );
  }
  return (
    <>
      <div className="agent-runtime-summary">
        <span>{visibilityLabel(instance.visibility, t)}</span>
        <strong>{instance.model_routing_key ?? t("agentsPolicyDefault")}</strong>
        <small>
          {agentDisplayName(instance, locale)} · {instance.model_key ?? t("agentsModelSelectedByPolicy")} ·{" "}
          {instance.status}
        </small>
      </div>
      {instance.runnable === false && (
        <div className="agent-runtime-readiness-warning">
          <strong>{t("agentsRuntimeReadinessWarning")}</strong>
          <span>{readinessReasonLabels(instance.readiness_reasons ?? [], t).join(" / ")}</span>
        </div>
      )}
    </>
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
  return t("agentsRuntimeInstance");
}
