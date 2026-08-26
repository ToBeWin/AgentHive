import { Button, PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type {
  MediaGenerationJobEvent,
  MediaGenerationJobResponse,
  MediaGenerationPlan,
  MediaModelCapability,
} from "../../lib/api";
import { MediaGenerationForm } from "./MediaGenerationForm";
import { MediaJobDetailsPanel } from "./MediaJobDetailsPanel";
import { MediaJobsTable } from "./MediaJobsTable";
import { MediaModelCapabilitiesPanel } from "./MediaModelCapabilitiesPanel";
import { MediaPlanPreviewPanel } from "./MediaPlanPreviewPanel";
import { formatDateTime, type MediaJobFormState } from "./mediaUtils";

export type MediaComposeStep = "configure" | "plan";
export type MediaJobsTab = "queue" | "details";

interface MediaComposeWorkspaceProps {
  canConfigureModelRoute: boolean;
  composeStep: MediaComposeStep;
  form: MediaJobFormState;
  models: MediaModelCapability[];
  onCreateJob: () => void;
  onFormChange: (form: MediaJobFormState) => void;
  onPlanRetry: () => void;
  onPreviewPlan: () => void;
  onStepChange: (step: MediaComposeStep) => void;
  plan: MediaGenerationPlan | null;
  planError: string | null;
  planning: boolean;
  saving: boolean;
}

export function MediaComposeWorkspace({
  canConfigureModelRoute,
  composeStep,
  form,
  models,
  onCreateJob,
  onFormChange,
  onPlanRetry,
  onPreviewPlan,
  onStepChange,
  plan,
  planError,
  planning,
  saving,
}: MediaComposeWorkspaceProps) {
  const { t } = useLocale();

  return (
    <div className="nested-workspace media-compose-workspace">
      <PageTabs
        active={composeStep}
        onChange={onStepChange}
        tabs={[
          {
            id: "configure",
            label: t("mediaComposeStepConfigure"),
            description: t(
              canConfigureModelRoute ? "mediaComposeStepConfigureDesc" : "mediaComposeStepConfigureDescEmployee",
            ),
          },
          {
            id: "plan",
            label: t("mediaComposeStepPlan"),
            description: t(canConfigureModelRoute ? "mediaComposeStepPlanDesc" : "mediaComposeStepPlanDescEmployee"),
          },
        ]}
      />
      {composeStep === "configure" && (
        <div className="grid media-compose-layout">
          <MediaGenerationForm
            canConfigureModelRoute={canConfigureModelRoute}
            form={form}
            models={models}
            onChange={onFormChange}
            onPlan={onPreviewPlan}
            onSubmit={onCreateJob}
            planning={planning}
            saving={saving}
          />
        </div>
      )}
      {composeStep === "plan" && (
        <div className="media-compose-stack">
          <MediaPlanPreviewPanel
            canInspectDiagnostics={canConfigureModelRoute}
            error={planError}
            loading={planning}
            onRetry={onPlanRetry}
            plan={plan}
          />
          <div className="media-plan-actions">
            <Button onClick={() => onStepChange("configure")}>{t("mediaBackToBrief")}</Button>
            <Button variant="primary" onClick={onCreateJob} disabled={!plan || planning || saving}>
              {saving ? t("mediaCreatingJob") : t("mediaCreateFromPlan")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

interface MediaJobsWorkspaceProps {
  actionJobId: string | null;
  activeJobsTab: MediaJobsTab;
  autoRefreshingJobs: boolean;
  canOperateJobs: boolean;
  events: MediaGenerationJobEvent[];
  eventsError: string | null;
  eventsLoading: boolean;
  jobs: MediaGenerationJobResponse[];
  jobsError: string | null;
  jobsLoading: boolean;
  lastJobsRefreshAt: string | null;
  onCancel: (job: MediaGenerationJobResponse) => void;
  onEnqueue: (job: MediaGenerationJobResponse) => void;
  onJobsTabChange: (tab: MediaJobsTab) => void;
  onPoll: (job: MediaGenerationJobResponse) => void;
  onPollBatch: () => void;
  onPollEnqueue: (job: MediaGenerationJobResponse) => void;
  onRefresh: () => void;
  onRetry: (job: MediaGenerationJobResponse) => void;
  onRun: (job: MediaGenerationJobResponse) => void;
  onSelectJob: (job: MediaGenerationJobResponse) => void;
  selectedJob: MediaGenerationJobResponse | null;
}

export function MediaJobsWorkspace({
  actionJobId,
  activeJobsTab,
  autoRefreshingJobs,
  canOperateJobs,
  events,
  eventsError,
  eventsLoading,
  jobs,
  jobsError,
  jobsLoading,
  lastJobsRefreshAt,
  onCancel,
  onEnqueue,
  onJobsTabChange,
  onPoll,
  onPollBatch,
  onPollEnqueue,
  onRefresh,
  onRetry,
  onRun,
  onSelectJob,
  selectedJob,
}: MediaJobsWorkspaceProps) {
  const { t } = useLocale();
  const refreshState = autoRefreshingJobs
    ? t("mediaAutoRefreshActive")
    : lastJobsRefreshAt
      ? t("mediaLastRefreshed").replace("{{time}}", formatDateTime(lastJobsRefreshAt))
      : "";

  return (
    <>
      <PageTabs
        active={activeJobsTab}
        onChange={onJobsTabChange}
        tabs={[
          {
            id: "queue",
            label: t(canOperateJobs ? "mediaJobsTabQueue" : "mediaJobsTabQueueEmployee"),
            description: t(canOperateJobs ? "mediaJobsTabQueueDesc" : "mediaJobsTabQueueDescEmployee"),
          },
          {
            id: "details",
            label: t("mediaJobsTabDetails"),
            description: t(canOperateJobs ? "mediaJobsTabDetailsDesc" : "mediaJobsTabDetailsDescEmployee"),
          },
        ]}
      />
      {activeJobsTab === "queue" && (
        <MediaJobsTable
          actionJobId={actionJobId}
          canOperateJobs={canOperateJobs}
          error={jobsError}
          jobs={jobs}
          loading={jobsLoading}
          onCancel={onCancel}
          onEnqueue={onEnqueue}
          onRefresh={onRefresh}
          onPoll={onPoll}
          onPollBatch={onPollBatch}
          onPollEnqueue={onPollEnqueue}
          onRetry={onRetry}
          onRun={onRun}
          onSelect={onSelectJob}
          refreshState={refreshState}
          selectedJobId={selectedJob?.id ?? null}
        />
      )}
      {activeJobsTab === "details" && (
        <MediaJobDetailsPanel
          canInspectExecution={canOperateJobs}
          events={events}
          eventsError={eventsError}
          eventsLoading={eventsLoading}
          job={selectedJob}
        />
      )}
    </>
  );
}

interface MediaModelsWorkspaceProps {
  error: string | null;
  loading: boolean;
  models: MediaModelCapability[];
  onRetry: () => void;
}

export function MediaModelsWorkspace({ error, loading, models, onRetry }: MediaModelsWorkspaceProps) {
  return <MediaModelCapabilitiesPanel error={error} loading={loading} models={models} onRetry={onRetry} />;
}
