import { Boxes, CheckCircle2, ClipboardList, Image, type LucideIcon, Sparkles, Video } from "lucide-react";
import { useState } from "react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { MediaGenerationJobResponse, MediaGenerationPlan, MediaModelCapability } from "../../lib/api";
import type { MediaComposeStep } from "./MediaWorkspaces";
import type { MediaJobFormState } from "./mediaUtils";
import type { MediaPageTab } from "./useMediaPageController";

type MediaLoopStageId = "models" | "brief" | "assets" | "plan" | "jobs";

interface MediaGenerationLoopPanelProps {
  activeTab: MediaPageTab;
  canConfigureModelRoute: boolean;
  composeStep: MediaComposeStep;
  form: MediaJobFormState;
  jobs: MediaGenerationJobResponse[];
  models: MediaModelCapability[];
  onOpenConfigure: () => void;
  onOpenJobs: () => void;
  onOpenModels: () => void;
  onOpenPlan: () => void;
  plan: MediaGenerationPlan | null;
  selectedJob: MediaGenerationJobResponse | null;
}

export function MediaGenerationLoopPanel({
  activeTab,
  canConfigureModelRoute,
  composeStep,
  form,
  jobs,
  models,
  onOpenConfigure,
  onOpenJobs,
  onOpenModels,
  onOpenPlan,
  plan,
  selectedJob,
}: MediaGenerationLoopPanelProps) {
  const { t } = useLocale();
  const activeModels = models.filter((model) => model.status === "active");
  const activeKindModels = activeModels.filter((model) => model.kind === form.kind);
  const imageReady = activeModels.some((model) => model.kind === "image");
  const videoReady = activeModels.some((model) => model.kind === "video");
  const hasPrompt = Boolean(form.prompt.trim());
  const hasReference = Boolean(form.referenceUrl.trim());
  const hasOutputSpec =
    Boolean(form.resolution) && (form.kind === "image" ? form.imageCount > 0 : form.durationSeconds > 0);
  const runningJobs = jobs.filter((job) => job.status === "queued" || job.status === "running").length;
  const succeededJobs = jobs.filter((job) => job.status === "succeeded").length;
  const selectedHasOutput = (selectedJob?.outputs.length ?? 0) > 0;
  const stages: Array<{
    action: () => void;
    detail: string;
    icon: LucideIcon;
    id: MediaLoopStageId;
    metric: string;
    status: string;
    title: string;
    tone: "ok" | "warning" | "blocked";
  }> = [
    {
      action: onOpenModels,
      detail: t("mediaLoopModelsDetail")
        .replace("{{image}}", imageReady ? t("commonYes") : t("commonNo"))
        .replace("{{video}}", videoReady ? t("commonYes") : t("commonNo")),
      icon: form.kind === "video" ? Video : Image,
      id: "models",
      metric: t("mediaLoopModelsMetric").replace("{{count}}", String(activeKindModels.length)),
      status: activeKindModels.length ? t("mediaLoopReady") : t("mediaLoopNeedsRoute"),
      title: t(canConfigureModelRoute ? "mediaLoopModels" : "mediaLoopCapability"),
      tone: activeKindModels.length ? "ok" : "blocked",
    },
    {
      action: onOpenConfigure,
      detail: t("mediaLoopBriefDetail").replace("{{mode}}", t(`mediaMode${modeSuffix(form.mode)}`)),
      icon: Sparkles,
      id: "brief",
      metric: hasPrompt ? t("mediaLoopBriefReady") : t("mediaLoopBriefMissing"),
      status: hasPrompt ? t("mediaLoopReady") : t("mediaLoopNeedsBrief"),
      title: t("mediaLoopBrief"),
      tone: hasPrompt ? "ok" : "blocked",
    },
    {
      action: onOpenConfigure,
      detail: t("mediaLoopAssetsDetail")
        .replace("{{references}}", hasReference ? "1" : "0")
        .replace("{{resolution}}", form.resolution || "-"),
      icon: Boxes,
      id: "assets",
      metric: hasOutputSpec ? t("mediaLoopOutputReady") : t("mediaLoopOutputMissing"),
      status: hasOutputSpec ? t("mediaLoopReady") : t("mediaLoopNeedsOutput"),
      title: t("mediaLoopAssets"),
      tone: hasOutputSpec ? (hasReference ? "ok" : "warning") : "blocked",
    },
    {
      action: onOpenPlan,
      detail: plan
        ? t("mediaLoopPlanDetail")
            .replace("{{cost}}", `$${plan.estimated_cost_usd}`)
            .replace("{{route}}", plan.routing_key)
        : t("mediaLoopPlanMissingDetail"),
      icon: ClipboardList,
      id: "plan",
      metric: plan ? t("mediaLoopPlanReady") : t("mediaLoopPlanMissing"),
      status: plan ? t("mediaLoopReady") : t("mediaLoopNeedsPlan"),
      title: t("mediaLoopPlan"),
      tone: plan ? "ok" : hasPrompt && activeKindModels.length ? "warning" : "blocked",
    },
    {
      action: onOpenJobs,
      detail: t("mediaLoopJobsDetail")
        .replace("{{running}}", String(runningJobs))
        .replace("{{succeeded}}", String(succeededJobs)),
      icon: CheckCircle2,
      id: "jobs",
      metric: selectedHasOutput ? t("mediaLoopResultReady") : t("mediaLoopResultPending"),
      status: selectedHasOutput ? t("mediaLoopReady") : jobs.length ? t("mediaLoopInProgress") : t("mediaLoopNeedsJob"),
      title: t("mediaLoopJobs"),
      tone: selectedHasOutput ? "ok" : jobs.length ? "warning" : "blocked",
    },
  ];
  const preferredStageId =
    stages.find((stage) => stage.tone === "blocked")?.id ??
    stages.find((stage) => stage.tone === "warning")?.id ??
    activeStageId(activeTab, composeStep);
  const [selectedStageId, setSelectedStageId] = useState<MediaLoopStageId>(() => preferredStageId);
  const selectedStage = stages.find((stage) => stage.id === selectedStageId) ?? stages[0];
  const SelectedIcon = selectedStage.icon;
  const readyCount = stages.filter((stage) => stage.tone === "ok").length;
  const reviewCount = stages.filter((stage) => stage.tone === "warning").length;
  const blockedCount = stages.filter((stage) => stage.tone === "blocked").length;

  return (
    <details className="media-generation-loop" aria-label={t("mediaLoopTitle")}>
      <summary className="media-generation-loop-summary">
        <div>
          <span>{t("mediaLoopEyebrow")}</span>
          <strong>{t("mediaLoopTitle")}</strong>
          <small>{t("mediaLoopCollapseHint")}</small>
        </div>
        <div className="media-generation-loop-summary-status">
          <StatusBadge label={t("mediaLoopReadyCount").replace("{{count}}", String(readyCount))} status="ok" />
          {reviewCount > 0 && (
            <StatusBadge label={t("mediaLoopReviewCount").replace("{{count}}", String(reviewCount))} status="warning" />
          )}
          {blockedCount > 0 && (
            <StatusBadge
              label={t("mediaLoopBlockedCount").replace("{{count}}", String(blockedCount))}
              status="blocked"
            />
          )}
        </div>
      </summary>
      <p className="media-generation-loop-description">
        {t(canConfigureModelRoute ? "mediaLoopDescription" : "mediaLoopDescriptionEmployee")}
      </p>
      <div className="media-generation-loop-workspace">
        <div className="media-generation-loop-steps" role="tablist" aria-label={t("mediaLoopStageTabs")}>
          {stages.map((stage) => {
            const Icon = stage.icon;
            return (
              <button
                aria-selected={stage.id === selectedStage.id}
                className={cx(
                  "media-generation-loop-step",
                  stage.tone,
                  stage.id === activeStageId(activeTab, composeStep) && "active-workspace",
                  stage.id === selectedStage.id && "selected",
                )}
                key={stage.id}
                onClick={() => setSelectedStageId(stage.id)}
                role="tab"
                type="button"
              >
                <span className="media-generation-loop-index">
                  <Icon size={16} />
                </span>
                <span>
                  <strong>{stage.title}</strong>
                  <small>{stage.status}</small>
                </span>
              </button>
            );
          })}
        </div>
        <div className={cx("media-generation-loop-detail", selectedStage.tone)} role="tabpanel">
          <div className="media-generation-loop-detail-head">
            <span className="media-generation-loop-icon">
              <SelectedIcon size={18} />
            </span>
            <div>
              <span>{t("mediaLoopSelectedStage")}</span>
              <strong>{selectedStage.title}</strong>
              <small>{selectedStage.detail}</small>
            </div>
            <StatusBadge label={selectedStage.status} status={selectedStage.tone} />
          </div>
          <div className="media-generation-loop-detail-metric">
            <span>{t("mediaLoopCurrentMetric")}</span>
            <strong>{selectedStage.metric}</strong>
          </div>
          <button className="button" onClick={selectedStage.action} type="button">
            {t("mediaLoopOpenStep")}
          </button>
        </div>
      </div>
      {selectedHasOutput && (
        <div className="media-generation-loop-note">
          <CheckCircle2 size={15} />
          <span>{t("mediaLoopReadyHint")}</span>
        </div>
      )}
    </details>
  );
}

function activeStageId(activeTab: MediaPageTab, composeStep: MediaComposeStep): MediaLoopStageId {
  if (activeTab === "models") {
    return "models";
  }
  if (activeTab === "jobs") {
    return "jobs";
  }
  return composeStep === "plan" ? "plan" : "brief";
}

function modeSuffix(mode: MediaJobFormState["mode"]) {
  if (mode === "material_breakdown") {
    return "MaterialBreakdown";
  }
  if (mode === "natural_language") {
    return "NaturalLanguage";
  }
  return "ManualPrompt";
}
