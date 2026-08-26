import { useState } from "react";
import { PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { MediaGenerationPlan } from "../../lib/api";
import { safeJson } from "./mediaUtils";

type MediaPlanDiagnosticsTab = "parameters" | "storage" | "execution";

export function MediaPlanDiagnosticsPanel({ plan }: { plan: MediaGenerationPlan }) {
  const { t } = useLocale();
  const [activeTab, setActiveTab] = useState<MediaPlanDiagnosticsTab>("parameters");

  return (
    <div className="nested-workspace">
      <PageTabs
        active={activeTab}
        onChange={setActiveTab}
        tabs={[
          {
            id: "parameters",
            label: t("mediaPlanTabParameters"),
            description: t("mediaPlanTabParametersDesc"),
          },
          {
            id: "storage",
            label: t("mediaPlanTabStorage"),
            description: t("mediaPlanTabStorageDesc"),
          },
          {
            id: "execution",
            label: t("mediaPlanTabExecution"),
            description: t("mediaPlanTabExecutionDesc"),
          },
        ]}
      />
      {activeTab === "parameters" && (
        <PlanBlock title={t("mediaParameters")} value={safeJson(plan.normalized_parameters)} />
      )}
      {activeTab === "storage" && <PlanBlock title={t("mediaStorage")} value={safeJson(plan.output_storage)} />}
      {activeTab === "execution" && <PlanBlock title={t("mediaExecution")} value={safeJson(plan.execution)} />}
    </div>
  );
}

function PlanBlock({ title, value }: { title: string; value: string }) {
  return (
    <article className="media-detail-block">
      <strong>{title}</strong>
      <pre>{value}</pre>
    </article>
  );
}
