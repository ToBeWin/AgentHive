import { Eye, Play, RefreshCw, RotateCcw, SendHorizontal, XCircle } from "lucide-react";
import { ApiNotice, Button, cx, LoadingState, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { MediaGenerationJobResponse } from "../../lib/api";
import { formatDateTime, kindLabelKey, modeLabelKey, shortId, statusLabelKey } from "./mediaUtils";

export function MediaJobsTable({
  actionJobId,
  canOperateJobs,
  error,
  jobs,
  loading,
  onEnqueue,
  onCancel,
  onRefresh,
  onPoll,
  onPollBatch,
  onPollEnqueue,
  onRetry,
  onRun,
  onSelect,
  refreshState,
  selectedJobId,
}: {
  actionJobId: string | null;
  canOperateJobs: boolean;
  error: string | null;
  jobs: MediaGenerationJobResponse[];
  loading: boolean;
  onEnqueue: (job: MediaGenerationJobResponse) => void;
  onCancel: (job: MediaGenerationJobResponse) => void;
  onRefresh: () => void;
  onPoll: (job: MediaGenerationJobResponse) => void;
  onPollBatch: () => void;
  onPollEnqueue: (job: MediaGenerationJobResponse) => void;
  onRetry: (job: MediaGenerationJobResponse) => void;
  onRun: (job: MediaGenerationJobResponse) => void;
  onSelect: (job: MediaGenerationJobResponse) => void;
  refreshState: string;
  selectedJobId: string | null;
}) {
  const { t } = useLocale();
  const pollableCount = jobs.filter((job) => job.status === "running" && Boolean(job.external_job_id)).length;
  const batchBusy = actionJobId === "batch-poll";
  const columnCount = canOperateJobs ? 5 : 4;
  return (
    <section className="panel media-jobs-panel">
      <div className="panel-heading">
        <div>
          <h2>{t(canOperateJobs ? "mediaJobsTitle" : "mediaJobsEmployeeTitle")}</h2>
          <p>{t(canOperateJobs ? "mediaJobsSubtitle" : "mediaJobsEmployeeSubtitle")}</p>
          {refreshState && <span className="media-refresh-state">{refreshState}</span>}
        </div>
        <div className="table-actions">
          {canOperateJobs && (
            <Button onClick={onPollBatch} disabled={pollableCount === 0 || batchBusy}>
              <SendHorizontal size={16} /> {t("mediaEnqueueAllPolls")} {pollableCount}
            </Button>
          )}
          <Button onClick={onRefresh}>
            <RefreshCw size={16} /> {t("mediaRefresh")}
          </Button>
        </div>
      </div>
      {error && (
        <ApiNotice
          title={t("mediaJobsUnavailable")}
          message={error}
          action={<Button onClick={onRefresh}>{t("commonRetry")}</Button>}
        />
      )}
      <table className="data-table compact-table">
        <thead>
          <tr>
            <th>{t("mediaJob")}</th>
            <th>{t("mediaStatus")}</th>
            {canOperateJobs && <th>{t("mediaProvider")}</th>}
            <th>{t("mediaCreated")}</th>
            <th>{t("mediaActions")}</th>
          </tr>
        </thead>
        <tbody>
          {loading && !jobs.length && (
            <tr>
              <td colSpan={columnCount}>
                <LoadingState lines={3} />
              </td>
            </tr>
          )}
          {!loading && !jobs.length && (
            <tr>
              <td colSpan={columnCount}>{t("mediaJobsEmpty")}</td>
            </tr>
          )}
          {jobs.map((job) => {
            const runnable = job.status === "queued" || job.status === "running";
            const pollable = job.status === "running" && Boolean(job.external_job_id);
            const retryable = job.status === "failed" || job.status === "canceled";
            const busy = actionJobId === job.id;
            const detailsLabel = `${t("mediaViewDetails")}: ${t(kindLabelKey(job.kind))} ${shortId(job.id)}`;
            return (
              <tr className={cx(selectedJobId === job.id && "selected-row")} key={job.id}>
                <td>
                  <strong>{t(kindLabelKey(job.kind))}</strong>
                  <span className="row-subtitle">
                    {shortId(job.id)} · {t(modeLabelKey(job.mode))}
                  </span>
                </td>
                <td>
                  <StatusBadge label={t(statusLabelKey(job.status))} status={job.status} />
                  {job.error_message && (
                    <span className="row-subtitle">
                      {t(canOperateJobs ? "mediaProviderNotConfigured" : "mediaJobNeedsAdminAttention")}
                    </span>
                  )}
                </td>
                {canOperateJobs && (
                  <td>
                    {job.provider_key}
                    <span className="row-subtitle">{job.model_key}</span>
                  </td>
                )}
                <td>{formatDateTime(job.created_at)}</td>
                <td>
                  <div className="table-actions">
                    {canOperateJobs && (
                      <>
                        <Button
                          onClick={(event) => {
                            event.stopPropagation();
                            onEnqueue(job);
                          }}
                          disabled={!runnable || busy}
                        >
                          <SendHorizontal size={15} /> {t("mediaEnqueue")}
                        </Button>
                        <Button
                          onClick={(event) => {
                            event.stopPropagation();
                            onRun(job);
                          }}
                          disabled={!runnable || busy}
                        >
                          <Play size={15} /> {t("mediaRunNow")}
                        </Button>
                        <Button
                          onClick={(event) => {
                            event.stopPropagation();
                            onRetry(job);
                          }}
                          disabled={!retryable || busy}
                        >
                          <RotateCcw size={15} /> {t("mediaRetry")}
                        </Button>
                        <Button
                          onClick={(event) => {
                            event.stopPropagation();
                            onPoll(job);
                          }}
                          disabled={!pollable || busy}
                        >
                          <RefreshCw size={15} /> {t("mediaPollStatus")}
                        </Button>
                        <Button
                          onClick={(event) => {
                            event.stopPropagation();
                            onPollEnqueue(job);
                          }}
                          disabled={!pollable || busy}
                        >
                          <SendHorizontal size={15} /> {t("mediaEnqueuePoll")}
                        </Button>
                        <Button
                          variant="ghost"
                          onClick={(event) => {
                            event.stopPropagation();
                            onCancel(job);
                          }}
                          disabled={!runnable || busy}
                        >
                          <XCircle size={15} /> {t("mediaCancel")}
                        </Button>
                      </>
                    )}
                    <button
                      type="button"
                      className="button secondary"
                      aria-label={detailsLabel}
                      onClick={() => onSelect(job)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          onSelect(job);
                        }
                      }}
                    >
                      <Eye size={15} aria-hidden="true" /> {t("mediaViewDetails")}
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}
