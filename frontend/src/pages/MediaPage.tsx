import { RefreshCw } from "lucide-react";
import { useEffect } from "react";
import { Button, cx, PageHeader, PageTabs } from "../components/app-ui";
import type { WorkspaceId } from "../data";
import { useLocale } from "../i18n-context";
import { MediaGenerationLoopPanel } from "./media/MediaGenerationLoopPanel";
import { MediaComposeWorkspace, MediaJobsWorkspace, MediaModelsWorkspace } from "./media/MediaWorkspaces";
import { useMediaPageController } from "./media/useMediaPageController";

export function MediaPage({
  activeWorkspace = "admin",
  isPrototype = false,
}: {
  activeWorkspace?: WorkspaceId;
  isPrototype?: boolean;
}) {
  const { t } = useLocale();
  const showModelRoutes = activeWorkspace !== "user";
  const canOperateJobs = activeWorkspace !== "user";
  const isUserWorkspace = activeWorkspace === "user";
  const media = useMediaPageController({ autoEnqueueOnCreate: isUserWorkspace, isPrototype });
  const activeTab = media.activeTab;
  const setActiveTab = media.setActiveTab;
  const openMediaConfigure = () => {
    media.setActiveTab("compose");
    media.setComposeStep("configure");
  };
  const openMediaPlan = () => {
    media.setActiveTab("compose");
    media.setComposeStep("plan");
    if (!media.plan && media.form.prompt.trim()) {
      void media.previewPlan();
    }
  };
  const openMediaJobs = () => {
    media.setActiveTab("jobs");
    media.setActiveJobsTab(media.selectedJob ? "details" : "queue");
  };
  const openMediaModels = () => {
    if (showModelRoutes) {
      media.setActiveTab("models");
      return;
    }
    media.setActiveTab("compose");
    media.setComposeStep("configure");
  };
  const handleTabChange = (nextTab: string) => {
    if (nextTab === "compose" || nextTab === "jobs" || (showModelRoutes && nextTab === "models")) {
      setActiveTab(nextTab);
    }
  };
  const tabs = [
    {
      id: "compose",
      label: t("mediaTabCompose"),
      description: t(isUserWorkspace ? "mediaTabComposeDescEmployee" : "mediaTabComposeDesc"),
    },
    {
      id: "jobs",
      label: t("mediaTabJobs"),
      description: t(isUserWorkspace ? "mediaTabJobsDescEmployee" : "mediaTabJobsDesc"),
    },
    ...(showModelRoutes ? [{ id: "models", label: t("mediaTabModels"), description: t("mediaTabModelsDesc") }] : []),
  ];

  useEffect(() => {
    if (!showModelRoutes && activeTab === "models") {
      setActiveTab("compose");
    }
  }, [activeTab, setActiveTab, showModelRoutes]);

  return (
    <section className="page">
      <PageHeader
        title={t("mediaTitle")}
        subtitle={t(isUserWorkspace ? "mediaSubtitleEmployee" : "mediaSubtitle")}
        actions={
          <Button onClick={media.refreshAll}>
            <RefreshCw size={16} /> {t("mediaRefresh")}
          </Button>
        }
      />
      {media.notice && (
        <div className={cx("form-message", media.noticeTone === "error" && "error")}>{media.notice}</div>
      )}
      <MediaGenerationLoopPanel
        activeTab={activeTab}
        canConfigureModelRoute={!isUserWorkspace}
        composeStep={media.composeStep}
        form={media.form}
        jobs={media.jobs}
        models={media.models}
        onOpenConfigure={openMediaConfigure}
        onOpenJobs={openMediaJobs}
        onOpenModels={openMediaModels}
        onOpenPlan={openMediaPlan}
        plan={media.plan}
        selectedJob={media.selectedJob}
      />
      <PageTabs active={activeTab} onChange={handleTabChange} tabs={tabs} />
      {activeTab === "compose" && (
        <MediaComposeWorkspace
          canConfigureModelRoute={!isUserWorkspace}
          composeStep={media.composeStep}
          form={media.form}
          models={media.models}
          onCreateJob={media.createJob}
          onFormChange={media.updateForm}
          onPlanRetry={media.previewPlan}
          onPreviewPlan={media.previewPlanAndShowResult}
          onStepChange={media.setComposeStep}
          plan={media.plan}
          planError={media.planError}
          planning={media.planning}
          saving={media.saving}
        />
      )}
      {activeTab === "jobs" && (
        <MediaJobsWorkspace
          actionJobId={media.actionJobId}
          activeJobsTab={media.activeJobsTab}
          autoRefreshingJobs={media.autoRefreshingJobs}
          canOperateJobs={canOperateJobs}
          events={media.jobEvents}
          eventsError={media.jobEventsError}
          eventsLoading={media.jobEventsLoading}
          jobs={media.jobs}
          jobsError={media.jobsError}
          jobsLoading={media.jobsLoading}
          lastJobsRefreshAt={media.lastJobsRefreshAt}
          onCancel={media.cancelJob}
          onEnqueue={media.enqueueJob}
          onJobsTabChange={media.setActiveJobsTab}
          onPoll={media.pollJob}
          onPollBatch={media.enqueueRunningPolls}
          onPollEnqueue={media.enqueuePollJob}
          onRefresh={() => void media.loadJobs()}
          onRetry={media.retryJob}
          onRun={media.runJob}
          onSelectJob={(job) => {
            media.setSelectedJobId(job.id);
            media.setActiveJobsTab("details");
          }}
          selectedJob={media.selectedJob}
        />
      )}
      {activeTab === "models" && (
        <MediaModelsWorkspace
          error={media.modelsError}
          loading={media.modelsLoading}
          models={media.models}
          onRetry={media.loadModels}
        />
      )}
    </section>
  );
}
