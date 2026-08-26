import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocale } from "../../i18n-context";
import {
  type MediaGenerationJobEvent,
  type MediaGenerationJobResponse,
  type MediaGenerationPlan,
  type MediaModelCapability,
  mediaApi,
} from "../../lib/api";
import type { MediaComposeStep, MediaJobsTab } from "./MediaWorkspaces";
import {
  defaultMediaJobForm,
  hasActiveMediaJobs,
  type MediaJobFormState,
  mediaGenerationRequestFromForm,
  prototypeJobFromRequest,
  prototypeMediaEvents,
  prototypeMediaJobs,
  prototypeMediaModels,
  prototypePlanFromRequest,
  transitionPrototypeMediaJob,
} from "./mediaUtils";

export type MediaPageTab = "compose" | "jobs" | "models";
export type MediaNoticeTone = "info" | "error";

export function useMediaPageController({
  autoEnqueueOnCreate = false,
  isPrototype = false,
}: {
  autoEnqueueOnCreate?: boolean;
  isPrototype?: boolean;
}) {
  const { t } = useLocale();
  const [activeTab, setActiveTab] = useState<MediaPageTab>("compose");
  const [composeStep, setComposeStep] = useState<MediaComposeStep>("configure");
  const [activeJobsTab, setActiveJobsTab] = useState<MediaJobsTab>("queue");
  const [models, setModels] = useState<MediaModelCapability[]>([]);
  const [jobs, setJobs] = useState<MediaGenerationJobResponse[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [form, setForm] = useState<MediaJobFormState>(defaultMediaJobForm);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [jobEvents, setJobEvents] = useState<MediaGenerationJobEvent[]>([]);
  const [jobEventsError, setJobEventsError] = useState<string | null>(null);
  const [jobEventsLoading, setJobEventsLoading] = useState(false);
  const [plan, setPlan] = useState<MediaGenerationPlan | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [noticeTone, setNoticeTone] = useState<MediaNoticeTone>("info");
  const [planning, setPlanning] = useState(false);
  const [saving, setSaving] = useState(false);
  const [actionJobId, setActionJobId] = useState<string | null>(null);
  const [lastJobsRefreshAt, setLastJobsRefreshAt] = useState<string | null>(null);
  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) ?? jobs[0] ?? null,
    [jobs, selectedJobId],
  );
  const autoRefreshingJobs = hasActiveMediaJobs(jobs);
  const showNotice = useCallback((message: string, tone: MediaNoticeTone = "info") => {
    setNotice(message);
    setNoticeTone(tone);
  }, []);
  const clearNotice = useCallback(() => {
    setNotice("");
    setNoticeTone("info");
  }, []);

  const loadModels = useCallback(async () => {
    setModelsLoading(true);
    setModelsError(null);
    if (isPrototype) {
      setModels(prototypeMediaModels);
      setModelsLoading(false);
      return;
    }
    try {
      setModels(await mediaApi.getModels());
    } catch (caught) {
      setModelsError(errorMessage(caught));
      if (isPrototype) {
        setModels(prototypeMediaModels);
      }
    } finally {
      setModelsLoading(false);
    }
  }, [isPrototype]);

  const loadJobs = useCallback(
    async ({ silent = false }: { silent?: boolean } = {}) => {
      if (!silent) {
        setJobsLoading(true);
      }
      setJobsError(null);
      if (isPrototype) {
        setJobs((currentJobs) => (currentJobs.length ? currentJobs : prototypeMediaJobs));
        setLastJobsRefreshAt(new Date().toISOString());
        if (!silent) {
          setJobsLoading(false);
        }
        return;
      }
      try {
        const response = await mediaApi.getGenerationJobs({ limit: 50 });
        setJobs(response.jobs);
        setLastJobsRefreshAt(new Date().toISOString());
      } catch (caught) {
        setJobsError(errorMessage(caught));
        if (isPrototype) {
          setJobs(prototypeMediaJobs);
        }
      } finally {
        if (!silent) {
          setJobsLoading(false);
        }
      }
    },
    [isPrototype],
  );

  useEffect(() => {
    void loadModels();
    void loadJobs();
  }, [loadJobs, loadModels]);

  useEffect(() => {
    if (!selectedJobId && jobs[0]) {
      setSelectedJobId(jobs[0].id);
    }
  }, [jobs, selectedJobId]);

  useEffect(() => {
    if (!selectedJob) {
      setJobEvents([]);
      setJobEventsError(null);
      return;
    }
    if (isPrototype) {
      setJobEvents(prototypeMediaEvents(selectedJob));
      setJobEventsError(null);
      setJobEventsLoading(false);
      return;
    }
    let cancelled = false;
    setJobEventsLoading(true);
    setJobEventsError(null);
    mediaApi
      .getGenerationJobEvents(selectedJob.id)
      .then((response) => {
        if (!cancelled) {
          setJobEvents(response.events);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setJobEventsError(errorMessage(caught));
          setJobEvents([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setJobEventsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [isPrototype, selectedJob]);

  useEffect(() => {
    if (isPrototype || !autoRefreshingJobs) {
      return;
    }
    let inFlight = false;
    const interval = window.setInterval(() => {
      if (inFlight) {
        return;
      }
      inFlight = true;
      void loadJobs({ silent: true }).finally(() => {
        inFlight = false;
      });
    }, 5000);
    return () => {
      window.clearInterval(interval);
    };
  }, [autoRefreshingJobs, isPrototype, loadJobs]);

  const refreshAll = () => {
    void loadModels();
    void loadJobs();
  };

  const updateForm = (nextForm: MediaJobFormState) => {
    setForm(nextForm);
    setPlan(null);
    setPlanError(null);
  };

  const previewPlan = async () => {
    setPlanning(true);
    setPlanError(null);
    clearNotice();
    if (isPrototype) {
      setPlan(prototypePlanFromRequest(mediaGenerationRequestFromForm(form), models));
      setPlanning(false);
      return;
    }
    try {
      setPlan(await mediaApi.planGeneration(mediaGenerationRequestFromForm(form)));
    } catch (caught) {
      setPlanError(errorMessage(caught));
    } finally {
      setPlanning(false);
    }
  };

  const previewPlanAndShowResult = () => {
    setComposeStep("plan");
    void previewPlan();
  };

  const createJob = async () => {
    setSaving(true);
    clearNotice();
    if (isPrototype) {
      const createdJob = prototypeJobFromRequest(mediaGenerationRequestFromForm(form), models);
      const created = autoEnqueueOnCreate ? transitionPrototypeMediaJob(createdJob, "enqueue") : createdJob;
      setJobs((currentJobs) => [created, ...currentJobs]);
      setSelectedJobId(created.id);
      setLastJobsRefreshAt(new Date().toISOString());
      showNotice(t(autoEnqueueOnCreate ? "mediaJobCreatedAndEnqueued" : "mediaJobCreated"));
      setActiveTab("jobs");
      setActiveJobsTab("details");
      setSaving(false);
      return;
    }
    try {
      const created = await mediaApi.createGenerationJob(mediaGenerationRequestFromForm(form));
      let noticeKey = "mediaJobCreated";
      if (autoEnqueueOnCreate) {
        try {
          await mediaApi.enqueueGenerationJob(created.id);
          noticeKey = "mediaJobCreatedAndEnqueued";
        } catch (caught) {
          showNotice(t("mediaJobCreatedQueueFailed").replace("{{reason}}", errorMessage(caught)), "error");
          setSelectedJobId(created.id);
          setActiveTab("jobs");
          setActiveJobsTab("details");
          await loadJobs();
          return;
        }
      }
      setSelectedJobId(created.id);
      showNotice(t(noticeKey));
      setActiveTab("jobs");
      setActiveJobsTab("details");
      await loadJobs();
    } catch (caught) {
      showNotice(errorMessage(caught), "error");
    } finally {
      setSaving(false);
    }
  };

  const enqueueJob = async (job: MediaGenerationJobResponse) => {
    if (isPrototype) {
      applyPrototypeJobTransition(job, "enqueue", t("mediaJobEnqueued"));
      return;
    }
    await withJobAction(job.id, async () => {
      const response = await mediaApi.enqueueGenerationJob(job.id);
      showNotice(
        response.queued ? t("mediaJobEnqueued") : queueReusedNotice("mediaJobEnqueueReused", response.task_id, t),
      );
    });
  };

  const runJob = async (job: MediaGenerationJobResponse) => {
    if (isPrototype) {
      applyPrototypeJobTransition(job, "run", t("mediaJobRun"));
      return;
    }
    await withJobAction(job.id, async () => {
      const updated = await mediaApi.runGenerationJob(job.id);
      setSelectedJobId(updated.id);
      showNotice(t("mediaJobRun"));
    });
  };

  const retryJob = async (job: MediaGenerationJobResponse) => {
    if (isPrototype) {
      applyPrototypeJobTransition(job, "retry", t("mediaJobRetried"));
      return;
    }
    await withJobAction(job.id, async () => {
      const updated = await mediaApi.retryGenerationJob(job.id);
      setSelectedJobId(updated.id);
      showNotice(t("mediaJobRetried"));
    });
  };

  const pollJob = async (job: MediaGenerationJobResponse) => {
    if (isPrototype) {
      applyPrototypeJobTransition(job, "poll", t("mediaJobPolled"));
      return;
    }
    await withJobAction(job.id, async () => {
      const updated = await mediaApi.pollGenerationJob(job.id);
      setSelectedJobId(updated.id);
      showNotice(t("mediaJobPolled"));
    });
  };

  const enqueuePollJob = async (job: MediaGenerationJobResponse) => {
    if (isPrototype) {
      applyPrototypeJobTransition(job, "enqueue_poll", t("mediaPollEnqueued"));
      return;
    }
    await withJobAction(job.id, async () => {
      const response = await mediaApi.enqueueGenerationPoll(job.id);
      showNotice(
        response.queued ? t("mediaPollEnqueued") : queueReusedNotice("mediaPollEnqueueReused", response.task_id, t),
      );
    });
  };

  const enqueueRunningPolls = async () => {
    setActionJobId("batch-poll");
    clearNotice();
    if (isPrototype) {
      let queued = 0;
      setJobs((currentJobs) =>
        currentJobs.map((job) => {
          if (job.status !== "running" || !job.external_job_id) {
            return job;
          }
          queued += 1;
          return transitionPrototypeMediaJob(job, "enqueue_poll");
        }),
      );
      setLastJobsRefreshAt(new Date().toISOString());
      showNotice(
        t("mediaBatchPollEnqueued")
          .replace("{{queued}}", String(queued))
          .replace("{{skipped}}", "0")
          .replace("{{failed}}", "0"),
      );
      setActionJobId(null);
      return;
    }
    try {
      const response = await mediaApi.enqueueRunningGenerationPolls(20);
      showNotice(
        t("mediaBatchPollEnqueued")
          .replace("{{queued}}", String(response.queued))
          .replace("{{skipped}}", String(response.skipped))
          .replace("{{failed}}", String(response.failed)),
      );
      await loadJobs();
    } catch (caught) {
      showNotice(errorMessage(caught), "error");
    } finally {
      setActionJobId(null);
    }
  };

  const cancelJob = async (job: MediaGenerationJobResponse) => {
    if (isPrototype) {
      applyPrototypeJobTransition(job, "cancel", t("mediaJobCanceled"));
      return;
    }
    await withJobAction(job.id, async () => {
      const updated = await mediaApi.cancelGenerationJob(job.id);
      setSelectedJobId(updated.id);
      showNotice(t("mediaJobCanceled"));
    });
  };

  const withJobAction = async (jobId: string, action: () => Promise<void>) => {
    setActionJobId(jobId);
    clearNotice();
    try {
      await action();
      await loadJobs();
    } catch (caught) {
      showNotice(errorMessage(caught), "error");
    } finally {
      setActionJobId(null);
    }
  };

  const applyPrototypeJobTransition = (
    job: MediaGenerationJobResponse,
    action: Parameters<typeof transitionPrototypeMediaJob>[1],
    message: string,
  ) => {
    setActionJobId(job.id);
    const updated = transitionPrototypeMediaJob(job, action);
    setJobs((currentJobs) => currentJobs.map((item) => (item.id === job.id ? updated : item)));
    setSelectedJobId(updated.id);
    setLastJobsRefreshAt(new Date().toISOString());
    showNotice(message);
    setActionJobId(null);
  };

  return {
    actionJobId,
    activeJobsTab,
    activeTab,
    autoRefreshingJobs,
    cancelJob,
    composeStep,
    createJob,
    enqueueJob,
    enqueuePollJob,
    enqueueRunningPolls,
    form,
    jobEvents,
    jobEventsError,
    jobEventsLoading,
    jobs,
    jobsError,
    jobsLoading,
    lastJobsRefreshAt,
    loadJobs,
    loadModels,
    models,
    modelsError,
    modelsLoading,
    notice,
    noticeTone,
    plan,
    planError,
    planning,
    pollJob,
    previewPlan,
    previewPlanAndShowResult,
    refreshAll,
    retryJob,
    runJob,
    saving,
    selectedJob,
    setActiveJobsTab,
    setActiveTab,
    setComposeStep,
    setSelectedJobId,
    updateForm,
  };
}

function queueReusedNotice(key: string, taskId: string, t: (key: string) => string) {
  return t(key).replace("{{taskId}}", taskId);
}

function errorMessage(caught: unknown) {
  return caught instanceof Error ? caught.message : "Request failed.";
}
