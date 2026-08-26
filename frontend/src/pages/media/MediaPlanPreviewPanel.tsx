import { Boxes } from "lucide-react";
import { useEffect, useState } from "react";
import { ApiNotice, Button, PageTabs, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { MediaGenerationPlan } from "../../lib/api";
import { MediaPlanDiagnosticsPanel } from "./MediaPlanDiagnosticsPanel";
import { MediaPlanSummaryPanel } from "./MediaPlanSummaryPanel";
import { kindLabelKey } from "./mediaUtils";

type MediaPlanTab = "summary" | "diagnostics";

export function MediaPlanPreviewPanel({
  canInspectDiagnostics,
  error,
  loading,
  onRetry,
  plan,
}: {
  canInspectDiagnostics: boolean;
  error: string | null;
  loading: boolean;
  onRetry: () => void;
  plan: MediaGenerationPlan | null;
}) {
  const { t } = useLocale();
  const [activeTab, setActiveTab] = useState<MediaPlanTab>("summary");
  useEffect(() => {
    if (!canInspectDiagnostics && activeTab === "diagnostics") {
      setActiveTab("summary");
    }
  }, [activeTab, canInspectDiagnostics]);

  return (
    <section className="panel media-plan-panel">
      <div className="panel-title-row">
        <div>
          <h2>{t("mediaPlanTitle")}</h2>
          <p>{t(canInspectDiagnostics ? "mediaPlanSubtitle" : "mediaPlanSubtitleEmployee")}</p>
        </div>
        {plan && <StatusBadge label={t(kindLabelKey(plan.kind))} status={plan.kind} />}
      </div>
      {error && (
        <ApiNotice
          title={t("mediaPlanUnavailable")}
          message={error}
          action={<Button onClick={onRetry}>{t("commonRetry")}</Button>}
        />
      )}
      {loading && <p className="inline-note">{t("mediaPlanLoading")}</p>}
      {!loading && !error && !plan && (
        <div className="media-empty-inline">
          <Boxes size={18} />
          <span>{t("mediaPlanEmpty")}</span>
        </div>
      )}
      {plan && (
        <div className="nested-workspace media-plan-workspace">
          <PageTabs
            active={activeTab}
            onChange={setActiveTab}
            tabs={[
              {
                id: "summary",
                label: t("mediaPlanTabSummary"),
                description: t(canInspectDiagnostics ? "mediaPlanTabSummaryDesc" : "mediaPlanTabSummaryDescEmployee"),
              },
              ...(canInspectDiagnostics
                ? [
                    {
                      id: "diagnostics" as const,
                      label: t("mediaPlanTabDiagnostics"),
                      description: t("mediaPlanTabDiagnosticsDesc"),
                    },
                  ]
                : []),
            ]}
          />
          {activeTab === "summary" && <MediaPlanSummaryPanel canInspectRoute={canInspectDiagnostics} plan={plan} />}
          {activeTab === "diagnostics" && <MediaPlanDiagnosticsPanel plan={plan} />}
        </div>
      )}
    </section>
  );
}
