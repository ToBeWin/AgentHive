import { CheckCircle2, CircleDashed } from "lucide-react";
import { cx, StatusBadge } from "../../components/app-ui";
import { usePrototypeSnapshot } from "../../hooks/admin/prototypeState";
import type { SystemDiagnostics } from "../../hooks/admin/system";
import { useLocale } from "../../i18n-context";
import type { SystemComponentReport } from "../../lib/api";

type ChecklistState = "done" | "warning" | "blocked";

interface ChecklistItem {
  id: string;
  label: string;
  description: string;
  state: ChecklistState;
}

export function DeploymentChecklistPanel({
  diagnostics,
  isPrototype,
}: {
  diagnostics: SystemDiagnostics | null;
  isPrototype: boolean;
}) {
  const { t } = useLocale();
  const snapshot = usePrototypeSnapshot();
  const components = diagnostics?.readiness.components ?? {};
  const items = [
    componentItem("runtime", t("settingsChecklistRuntime"), t("settingsChecklistRuntimeDetail"), components, [
      "database",
      "redis",
      "minio",
      "frontend",
    ]),
    componentItem("license", t("settingsChecklistLicense"), t("settingsChecklistLicenseDetail"), components, [
      "license_identity",
      "production_config",
    ]),
    componentItem("models", t("settingsChecklistModels"), t("settingsChecklistModelsDetail"), components, ["litellm"]),
    componentItem("knowledge", t("settingsChecklistKnowledge"), t("settingsChecklistKnowledgeDetail"), components, [
      "pgvector",
      "knowledge_runtime",
    ]),
    componentItem("channels", t("settingsChecklistChannels"), t("settingsChecklistChannelsDetail"), components, [
      "channel_gateway",
    ]),
    componentItem("governance", t("settingsChecklistGovernance"), t("settingsChecklistGovernanceDetail"), components, [
      "budget_governance",
      "audit_diagnostics",
    ]),
    {
      description: t("settingsChecklistDemoDetail")
        .replace("{{agents}}", String(snapshot.agentInstances.length))
        .replace("{{modules}}", String(snapshot.agentModules.filter((module) => module.enabled).length))
        .replace("{{knowledge}}", String(snapshot.knowledgeBases.length))
        .replace("{{channels}}", String(snapshot.channels.length)),
      id: "demo",
      label: t("settingsChecklistDemo"),
      state: isPrototype ? "done" : "warning",
    } satisfies ChecklistItem,
  ];
  const doneCount = items.filter((item) => item.state === "done").length;
  const percent = Math.round((doneCount / items.length) * 100);

  return (
    <section className="panel settings-checklist-panel">
      <div className="panel-title">
        <div>
          <h2>{t("settingsDeploymentChecklist")}</h2>
          <p>{t("settingsDeploymentChecklistHelp")}</p>
        </div>
        <StatusBadge status={percent === 100 ? "healthy" : "degraded"} label={`${percent}%`} />
      </div>
      <div
        aria-label={t("settingsDeploymentChecklistProgress")}
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={percent}
        className="settings-checklist-progress"
        role="progressbar"
      >
        <span style={{ width: `${percent}%` }} />
      </div>
      <div className="settings-checklist-grid">
        {items.map((item) => (
          <article className={cx("settings-checklist-item", `settings-checklist-${item.state}`)} key={item.id}>
            {item.state === "done" ? <CheckCircle2 size={18} /> : <CircleDashed size={18} />}
            <div>
              <strong>{item.label}</strong>
              <p>{item.description}</p>
            </div>
            <StatusBadge status={statusForState(item.state)} label={labelForState(item.state, t)} />
          </article>
        ))}
      </div>
    </section>
  );
}

function componentItem(
  id: string,
  label: string,
  description: string,
  components: Record<string, SystemComponentReport>,
  componentKeys: string[],
): ChecklistItem {
  const reports = componentKeys.map((key) => components[key]).filter(Boolean);
  if (!reports.length) {
    return { description, id, label, state: "warning" };
  }
  if (reports.some((report) => report.status === "unhealthy" || report.status === "error")) {
    return { description, id, label, state: "blocked" };
  }
  if (reports.some((report) => report.status === "degraded" || report.status === "not_configured")) {
    return { description, id, label, state: "warning" };
  }
  return { description, id, label, state: "done" };
}

function labelForState(state: ChecklistState, t: (key: string) => string) {
  if (state === "done") {
    return t("settingsChecklistDone");
  }
  if (state === "blocked") {
    return t("settingsChecklistBlocked");
  }
  return t("settingsChecklistReview");
}

function statusForState(state: ChecklistState) {
  if (state === "done") {
    return "healthy";
  }
  if (state === "blocked") {
    return "unhealthy";
  }
  return "degraded";
}
