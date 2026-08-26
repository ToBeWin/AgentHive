import { ClipboardList, Copy, Route, SendHorizontal, Sparkles } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { Button, cx, PageTabs, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { ChatMessageResponse, WorkbenchAgentInstanceResponse } from "../../lib/api";
import { AgentRuntimeBlocker } from "./AgentRuntimeBlocker";
import { workflowActionKeys, workflowInputKeys, workflowOutputKeys, workflowStepKeys } from "./agentCategory";
import { EmployeeMessageStream } from "./EmployeeMessageStream";
import { EmployeeTaskFlowPanel } from "./EmployeeTaskFlowPanel";
import { EmployeeTaskFocusBar, type EmployeeTaskTab } from "./EmployeeTaskFocusBar";
import { runtimePair } from "./employeeTaskRuntimeUtils";
import type { ActiveEmployeeTaskSummary } from "./useDigitalEmployeesController";

type EmployeeActionTab = "scenarios" | "shortcuts";

interface EmployeeTaskPanelProps {
  activeTaskSummary: ActiveEmployeeTaskSummary;
  canChat: boolean;
  canInspectEvidence: boolean;
  copiedResult: boolean;
  draft: string;
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
  latestAssistantMessage: ChatMessageResponse | undefined;
  messages: ChatMessageResponse[];
  onApplyStarter: (starterKey: string) => void;
  onCopyLatestAnswer: () => void;
  onDraftChange: (draft: string) => void;
  onRefineLatestAnswer: () => void;
  onSend: () => void;
  onShowAgents: () => void;
  onShowRunEvidence: () => void;
  scenarioLauncher?: ReactNode;
  selectedEmployee: WorkbenchAgentInstanceResponse | null;
  selectedWorkflowKey: string | null;
  sending: boolean;
}

export function EmployeeTaskPanel({
  activeTaskSummary,
  canChat,
  canInspectEvidence,
  copiedResult,
  draft,
  inputRef,
  latestAssistantMessage,
  messages,
  onApplyStarter,
  onCopyLatestAnswer,
  onDraftChange,
  onRefineLatestAnswer,
  onSend,
  onShowAgents,
  onShowRunEvidence,
  scenarioLauncher,
  selectedEmployee,
  selectedWorkflowKey,
  sending,
}: EmployeeTaskPanelProps) {
  const { locale, t } = useLocale();
  const [taskTab, setTaskTab] = useState<EmployeeTaskTab>("actions");
  const [actionTab, setActionTab] = useState<EmployeeActionTab>("scenarios");
  const selectedEmployeeId = selectedEmployee?.id ?? "";
  const latestAssistantMessageId = latestAssistantMessage?.id ?? "";
  const previousDraftRef = useRef(draft);
  const previousEmployeeIdRef = useRef(selectedEmployeeId);
  const awaitingResultRef = useRef(false);
  const inputSummary = workflowInputKeys(selectedEmployee)
    .map((key) => t(key))
    .join(" / ");
  const outputSummary = workflowOutputKeys(selectedEmployee)
    .map((key) => t(key))
    .join(" / ");
  const workflowSteps = workflowStepKeys(selectedEmployee);
  const workflowInputs = workflowInputKeys(selectedEmployee);
  const workflowOutputs = workflowOutputKeys(selectedEmployee);
  const agentRunnable = selectedEmployee?.runnable !== false;
  const hasUserTask = messages.some((message) => message.role !== "assistant" && message.content.trim());
  const progressSteps = taskProgressSteps({
    hasResult: activeTaskSummary.hasResult,
    hasSelectedEmployee: Boolean(selectedEmployee),
    hasUserTask,
    sending,
    t,
  });
  const applyStarter = (starterKey: string) => {
    setTaskTab("conversation");
    onApplyStarter(starterKey);
  };
  const refineResult = () => {
    setTaskTab("conversation");
    onRefineLatestAnswer();
  };
  const openConversation = () => {
    setTaskTab("conversation");
    window.requestAnimationFrame(() => inputRef.current?.focus());
  };

  useEffect(() => {
    if (previousEmployeeIdRef.current === selectedEmployeeId) {
      return;
    }
    previousEmployeeIdRef.current = selectedEmployeeId;
    setTaskTab(messages.length ? "conversation" : "actions");
    setActionTab("scenarios");
    awaitingResultRef.current = false;
  }, [messages.length, selectedEmployeeId]);

  useEffect(() => {
    const previousDraft = previousDraftRef.current;
    previousDraftRef.current = draft;
    if (taskTab !== "actions" || !draft.trim() || previousDraft === draft) {
      return;
    }
    setTaskTab("conversation");
  }, [draft, taskTab]);

  useEffect(() => {
    if (sending) {
      awaitingResultRef.current = true;
      return;
    }
    if (!awaitingResultRef.current || !latestAssistantMessageId || !activeTaskSummary.hasResult) {
      return;
    }
    awaitingResultRef.current = false;
    setTaskTab("result");
  }, [activeTaskSummary.hasResult, latestAssistantMessageId, sending]);

  return (
    <section className="employee-task-main">
      <div className="employee-task-tabs">
        <PageTabs
          active={taskTab}
          onChange={setTaskTab}
          tabs={[
            {
              id: "actions",
              label: t("digitalEmployeesTaskActionsTab"),
              description: t("digitalEmployeesTaskActionsTabDesc"),
            },
            {
              id: "conversation",
              label: t("digitalEmployeesTaskConversationTab"),
              description: t("digitalEmployeesTaskConversationTabDesc"),
            },
            {
              id: "result",
              label: t("digitalEmployeesTaskResultTab"),
              description: t("digitalEmployeesTaskResultTabDesc"),
            },
            {
              id: "context",
              label: t("digitalEmployeesTaskContextTab"),
              description: t("digitalEmployeesTaskContextTabDesc"),
            },
          ]}
        />
      </div>
      <EmployeeTaskFocusBar
        activeTab={taskTab}
        hasResult={activeTaskSummary.hasResult}
        hasUserTask={hasUserTask}
        onOpenActions={() => setTaskTab("actions")}
        onOpenConversation={openConversation}
        onOpenContext={() => setTaskTab("context")}
        onOpenResult={() => setTaskTab("result")}
        selectedWorkflowLabel={selectedWorkflowKey ? t(selectedWorkflowKey) : t("digitalEmployeesFocusNoWorkflow")}
        sending={sending}
      />

      {taskTab === "conversation" && (
        <>
          <details className="employee-task-summary" aria-label={t("digitalEmployeesTaskSummary")}>
            <summary>
              <div className="employee-task-summary-title">
                <span>{t("digitalEmployeesCurrentTask")}</span>
                <strong>{activeTaskSummary.title}</strong>
                <small>
                  {activeTaskSummary.workflowKey ? t(activeTaskSummary.workflowKey) : t("digitalEmployeesTaskManual")}
                </small>
              </div>
              <div className="employee-task-summary-metrics">
                <StatusBadge status={t(activeTaskSummary.statusKey)} />
                {canInspectEvidence ? (
                  <>
                    <span>
                      {t("digitalEmployeesTaskRoute")}:{" "}
                      {runtimePair(activeTaskSummary.providerKey, activeTaskSummary.modelKey)}
                    </span>
                    <span>
                      {t("digitalEmployeesTaskTokens")}: {activeTaskSummary.totalTokens}
                    </span>
                  </>
                ) : (
                  <span>
                    {t("digitalEmployeesTaskProgress")}:{" "}
                    {activeTaskSummary.hasResult
                      ? t("digitalEmployeesResultReady")
                      : t("digitalEmployeesTaskProgressWaiting")}
                  </span>
                )}
                {activeTaskSummary.completedAt ? (
                  <span>{formatCompletedAt(activeTaskSummary.completedAt, locale)}</span>
                ) : null}
              </div>
              <small className="employee-task-summary-hint">{t("digitalEmployeesTaskSummaryHint")}</small>
            </summary>
            <ul className="employee-task-progress-strip" aria-label={t("digitalEmployeesTaskProgress")}>
              {progressSteps.map((step) => (
                <li className={cx("employee-task-progress-step", step.state)} key={step.label}>
                  <i />
                  {step.label}
                </li>
              ))}
            </ul>
          </details>
          {selectedWorkflowKey && (
            <div className="employee-workflow-banner">
              <span>{t("digitalEmployeesSelectedWorkflow")}</span>
              <strong>{t(selectedWorkflowKey)}</strong>
              <small>{t("digitalEmployeesWorkflowGuardrail")}</small>
            </div>
          )}
          <EmployeeMessageStream
            canChat={canChat && agentRunnable}
            canInspectEvidence={canInspectEvidence}
            messages={messages}
            onApplyStarter={applyStarter}
            selectedEmployee={selectedEmployee}
            sending={sending}
            starterKeys={workflowActionKeys(selectedEmployee)}
          />

          {selectedEmployee && !agentRunnable && (
            <AgentRuntimeBlocker
              canInspectEvidence={canInspectEvidence}
              onShowRunEvidence={onShowRunEvidence}
              selectedEmployee={selectedEmployee}
            />
          )}

          {latestAssistantMessage?.content && (
            <section className="employee-result-handoff" aria-label={t("digitalEmployeesLatestResult")}>
              <div>
                <span>{t("digitalEmployeesLatestResult")}</span>
                <strong>{t("digitalEmployeesResultReadyHint")}</strong>
              </div>
              <div className="employee-result-actions">
                <button type="button" onClick={() => setTaskTab("result")}>
                  <ClipboardList size={15} />
                  {t("digitalEmployeesViewResult")}
                </button>
              </div>
            </section>
          )}

          <div className="employee-composer">
            <textarea
              ref={inputRef}
              disabled={!selectedEmployee || !canChat || !agentRunnable}
              onChange={(event) => onDraftChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  onSend();
                }
              }}
              placeholder={t("digitalEmployeesInputPlaceholder")}
              rows={1}
              value={draft}
            />
            <Button
              disabled={!selectedEmployee || !canChat || !agentRunnable || !draft.trim() || sending}
              onClick={onSend}
              variant="primary"
            >
              <SendHorizontal size={16} />{" "}
              {!agentRunnable
                ? t("digitalEmployeesAgentNotRunnableAction")
                : sending
                  ? t("digitalEmployeesSending")
                  : t("digitalEmployeesSend")}
            </Button>
          </div>
        </>
      )}

      {taskTab === "result" && (
        <div className="employee-result-view">
          <section className="employee-task-status" aria-label={t("digitalEmployeesLatestResult")}>
            <div>
              <span>{t("digitalEmployeesLatestResult")}</span>
              <strong>
                {activeTaskSummary.hasResult ? t("digitalEmployeesResultReady") : t("digitalEmployeesNoResultYet")}
              </strong>
            </div>
            <div className="employee-task-metrics">
              <StatusBadge status={t(activeTaskSummary.statusKey)} />
              {activeTaskSummary.completedAt ? (
                <small>{formatCompletedAt(activeTaskSummary.completedAt, locale)}</small>
              ) : null}
            </div>
          </section>

          <article className="employee-result-card">
            <span>{t("digitalEmployeesLatestResult")}</span>
            <p>{activeTaskSummary.latestAnswer || t("digitalEmployeesNoResultYet")}</p>
          </article>

          <div className="employee-result-actions">
            <button type="button" disabled={!latestAssistantMessage?.content} onClick={onCopyLatestAnswer}>
              <Copy size={15} />
              {copiedResult ? t("digitalEmployeesCopiedResult") : t("digitalEmployeesCopyResult")}
            </button>
            <button type="button" disabled={!latestAssistantMessage?.content || !canChat} onClick={refineResult}>
              <Sparkles size={15} />
              {t("digitalEmployeesRefineResult")}
            </button>
            {canInspectEvidence && (
              <button type="button" disabled={!latestAssistantMessage?.content} onClick={onShowRunEvidence}>
                <Route size={15} />
                {t("agentWorkbenchShowEvidence")}
              </button>
            )}
          </div>
        </div>
      )}

      {taskTab === "actions" && (
        <div className="employee-action-view">
          <div className="employee-action-tabs">
            <PageTabs
              active={actionTab}
              onChange={setActionTab}
              tabs={[
                {
                  id: "scenarios",
                  label: t("digitalEmployeesActionScenariosTab"),
                  description: t("digitalEmployeesActionScenariosTabDesc"),
                },
                {
                  id: "shortcuts",
                  label: t("digitalEmployeesActionShortcutsTab"),
                  description: t("digitalEmployeesActionShortcutsTabDesc"),
                },
              ]}
            />
          </div>

          {actionTab === "scenarios" && scenarioLauncher}

          {actionTab === "shortcuts" && (
            <section className="employee-workflow-shortcuts" aria-label={t("digitalEmployeesStarterTitle")}>
              <div className="employee-action-intro">
                <strong>{t("digitalEmployeesStarterTitle")}</strong>
                <span>{t("digitalEmployeesStarterBody")}</span>
              </div>
              <div className="employee-workflow-card-grid">
                {workflowActionKeys(selectedEmployee).map((starterKey) => (
                  <button
                    className={cx("employee-workflow-card", selectedWorkflowKey === starterKey && "selected")}
                    key={starterKey}
                    type="button"
                    disabled={!selectedEmployee || !canChat || !agentRunnable}
                    onClick={() => applyStarter(starterKey)}
                  >
                    <strong>{t(starterKey)}</strong>
                    <span>{t("digitalEmployeesWorkflowInputs").replace("{{items}}", inputSummary)}</span>
                    <small>{t("digitalEmployeesWorkflowOutputs").replace("{{items}}", outputSummary)}</small>
                  </button>
                ))}
              </div>
            </section>
          )}
        </div>
      )}

      {taskTab === "context" && (
        <div className="employee-context-view">
          <EmployeeTaskFlowPanel
            hasResult={activeTaskSummary.hasResult}
            hasUserTask={hasUserTask}
            onOpenAgents={onShowAgents}
            onOpenConversation={openConversation}
            onOpenResult={() => setTaskTab("result")}
            onOpenWorkflows={() => setTaskTab("actions")}
            selectedEmployee={selectedEmployee}
            selectedWorkflowKey={selectedWorkflowKey}
            sending={sending}
          />
          <section className="employee-context-brief" aria-label={t("digitalEmployeesTaskBrief")}>
            <div className="employee-context-brief-head">
              <span>
                <ClipboardList size={16} />
                {t("digitalEmployeesTaskBrief")}
              </span>
              <small>{t("digitalEmployeesTaskBriefHint")}</small>
            </div>
            <div className="employee-task-brief-grid">
              <section>
                <strong>{t("agentWorkbenchFlow")}</strong>
                <ol>
                  {workflowSteps.map((stepKey) => (
                    <li key={stepKey}>{t(stepKey)}</li>
                  ))}
                </ol>
              </section>
              <section>
                <strong>{t("agentWorkbenchInputs")}</strong>
                <div>
                  {workflowInputs.map((inputKey) => (
                    <span key={inputKey}>{t(inputKey)}</span>
                  ))}
                </div>
              </section>
              <section>
                <strong>{t("agentWorkbenchOutputs")}</strong>
                <div>
                  {workflowOutputs.map((outputKey) => (
                    <span key={outputKey}>{t(outputKey)}</span>
                  ))}
                </div>
              </section>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}

function taskProgressSteps({
  hasResult,
  hasSelectedEmployee,
  hasUserTask,
  sending,
  t,
}: {
  hasResult: boolean;
  hasSelectedEmployee: boolean;
  hasUserTask: boolean;
  sending: boolean;
  t: (key: string) => string;
}) {
  return [
    {
      label: t("digitalEmployeesProgressAgentReady"),
      state: hasSelectedEmployee ? "done" : "current",
    },
    {
      label: hasUserTask ? t("digitalEmployeesProgressTaskSent") : t("digitalEmployeesProgressDescribeTask"),
      state: hasUserTask ? "done" : hasSelectedEmployee ? "current" : "pending",
    },
    {
      label: hasResult
        ? t("digitalEmployeesProgressResultReady")
        : sending
          ? t("digitalEmployeesProgressGenerating")
          : t("digitalEmployeesTaskProgressWaiting"),
      state: hasResult ? "done" : sending ? "current" : "pending",
    },
  ];
}

function formatCompletedAt(value: string, locale: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(locale, {
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}
