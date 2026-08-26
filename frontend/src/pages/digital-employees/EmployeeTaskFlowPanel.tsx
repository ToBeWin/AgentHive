import {
  Bot,
  ChevronDown,
  ChevronRight,
  ClipboardCheck,
  type LucideIcon,
  MessageSquareText,
  Sparkles,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { WorkbenchAgentInstanceResponse } from "../../lib/api";

type EmployeeTaskFlowStep = "agent" | "workflow" | "task" | "result";

interface EmployeeTaskFlowPanelProps {
  hasResult: boolean;
  hasUserTask: boolean;
  onOpenAgents: () => void;
  onOpenConversation: () => void;
  onOpenResult: () => void;
  onOpenWorkflows: () => void;
  selectedEmployee: WorkbenchAgentInstanceResponse | null;
  selectedWorkflowKey: string | null;
  sending: boolean;
}

export function EmployeeTaskFlowPanel({
  hasResult,
  hasUserTask,
  onOpenAgents,
  onOpenConversation,
  onOpenResult,
  onOpenWorkflows,
  selectedEmployee,
  selectedWorkflowKey,
  sending,
}: EmployeeTaskFlowPanelProps) {
  const { t } = useLocale();
  const [expanded, setExpanded] = useState(!selectedEmployee);
  const selectedEmployeeId = selectedEmployee?.id ?? "";
  const previousEmployeeIdRef = useRef(selectedEmployeeId);
  const [selectedStepId, setSelectedStepId] = useState<EmployeeTaskFlowStep>("agent");
  const agentReady = Boolean(selectedEmployee) && selectedEmployee?.runnable !== false;
  const steps: Array<{
    action: () => void;
    detail: string;
    icon: LucideIcon;
    id: EmployeeTaskFlowStep;
    metric: string;
    status: string;
    title: string;
    tone: "ok" | "warning" | "blocked";
  }> = [
    {
      action: onOpenAgents,
      detail: agentReady ? t("digitalEmployeesFlowAgentReadyDetail") : t("digitalEmployeesFlowAgentMissingDetail"),
      icon: Bot,
      id: "agent",
      metric: selectedEmployee ? t("digitalEmployeesFlowAgentSelected") : t("digitalEmployeesFlowAgentMissing"),
      status: agentReady ? t("digitalEmployeesFlowReady") : t("digitalEmployeesFlowNeedsAgent"),
      title: t("digitalEmployeesFlowAgent"),
      tone: agentReady ? "ok" : "blocked",
    },
    {
      action: onOpenWorkflows,
      detail: selectedWorkflowKey
        ? t("digitalEmployeesFlowWorkflowSelectedDetail")
        : t("digitalEmployeesFlowWorkflowDetail"),
      icon: Sparkles,
      id: "workflow",
      metric: selectedWorkflowKey ? t(selectedWorkflowKey) : t("digitalEmployeesFlowWorkflowOptional"),
      status: selectedWorkflowKey ? t("digitalEmployeesFlowReady") : t("digitalEmployeesFlowOptional"),
      title: t("digitalEmployeesFlowWorkflow"),
      tone: selectedWorkflowKey ? "ok" : "warning",
    },
    {
      action: onOpenConversation,
      detail: hasUserTask ? t("digitalEmployeesFlowTaskSentDetail") : t("digitalEmployeesFlowTaskDetail"),
      icon: MessageSquareText,
      id: "task",
      metric: hasUserTask
        ? t("digitalEmployeesProgressTaskSent")
        : sending
          ? t("digitalEmployeesProgressGenerating")
          : t("digitalEmployeesProgressDescribeTask"),
      status: hasUserTask || sending ? t("digitalEmployeesFlowReady") : t("digitalEmployeesFlowNeedsTask"),
      title: t("digitalEmployeesFlowTask"),
      tone: hasUserTask || sending ? "ok" : agentReady ? "warning" : "blocked",
    },
    {
      action: onOpenResult,
      detail: hasResult ? t("digitalEmployeesFlowResultReadyDetail") : t("digitalEmployeesFlowResultDetail"),
      icon: ClipboardCheck,
      id: "result",
      metric: hasResult ? t("digitalEmployeesResultReady") : t("digitalEmployeesNoResultYet"),
      status: hasResult ? t("digitalEmployeesFlowReady") : t("digitalEmployeesFlowNeedsResult"),
      title: t("digitalEmployeesFlowResult"),
      tone: hasResult ? "ok" : hasUserTask || sending ? "warning" : "blocked",
    },
  ];
  const currentStep = steps.find((step) => step.tone !== "ok") ?? steps[steps.length - 1];
  const selectedStep = steps.find((step) => step.id === selectedStepId) ?? currentStep;
  const SelectedIcon = selectedStep.icon;

  useEffect(() => {
    if (previousEmployeeIdRef.current === selectedEmployeeId) {
      return;
    }
    previousEmployeeIdRef.current = selectedEmployeeId;
    if (selectedEmployeeId) {
      setExpanded(false);
    }
  }, [selectedEmployeeId]);

  useEffect(() => {
    setSelectedStepId(currentStep.id);
  }, [currentStep.id]);

  return (
    <section className={cx("employee-task-flow", !expanded && "compact")} aria-label={t("digitalEmployeesFlowTitle")}>
      <div className="employee-task-flow-head">
        <button
          aria-expanded={expanded}
          className="employee-task-flow-toggle"
          onClick={() => setExpanded((value) => !value)}
          type="button"
        >
          <span className="employee-task-flow-toggle-title">
            <span>{t("digitalEmployeesFlowEyebrow")}</span>
            <strong>{t("digitalEmployeesFlowTitle")}</strong>
          </span>
          <span className="employee-task-flow-current">
            <strong>{currentStep.title}</strong>
            <small>{currentStep.metric}</small>
          </span>
          <span className="employee-task-flow-toggle-action">
            {expanded ? t("digitalEmployeesFlowCollapse") : t("digitalEmployeesFlowExpand")}
            {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          </span>
        </button>
        {expanded ? <p>{t("digitalEmployeesFlowDescription")}</p> : null}
      </div>
      {!expanded && (
        <div className="employee-task-flow-compact-strip">
          {steps.map((step) => (
            <button
              className={cx("employee-task-flow-step-dot", step.tone)}
              key={step.id}
              onClick={step.action}
              type="button"
            >
              <i />
              <span>{step.title}</span>
              <small>{step.status}</small>
            </button>
          ))}
        </div>
      )}
      {expanded && (
        <div className="employee-task-flow-workspace">
          <div className="employee-task-flow-steps" role="tablist" aria-label={t("digitalEmployeesFlowStageTabs")}>
            {steps.map((step, index) => {
              const Icon = step.icon;
              const selected = selectedStep.id === step.id;
              return (
                <button
                  aria-selected={selected}
                  className={cx("employee-task-flow-step", step.tone, selected && "selected")}
                  key={step.id}
                  onClick={() => setSelectedStepId(step.id)}
                  role="tab"
                  type="button"
                >
                  <span className="employee-task-flow-index">{String(index + 1).padStart(2, "0")}</span>
                  <span className="employee-task-flow-icon">
                    <Icon size={17} />
                  </span>
                  <span>
                    <strong>{step.title}</strong>
                    <small>{step.status}</small>
                  </span>
                </button>
              );
            })}
          </div>
          <section
            aria-label={t("digitalEmployeesFlowSelectedStage")}
            className={cx("employee-task-flow-detail", selectedStep.tone)}
          >
            <div className="employee-task-flow-detail-head">
              <span className="employee-task-flow-icon">
                <SelectedIcon size={18} />
              </span>
              <div>
                <span>{t("digitalEmployeesFlowCurrentStage")}</span>
                <strong>{selectedStep.title}</strong>
              </div>
              <StatusBadge label={selectedStep.status} status={selectedStep.tone} />
            </div>
            <strong className="employee-task-flow-detail-metric">{selectedStep.metric}</strong>
            <p>{selectedStep.detail}</p>
            <button className="button" onClick={selectedStep.action} type="button">
              {t("digitalEmployeesFlowOpenStep")}
            </button>
          </section>
        </div>
      )}
    </section>
  );
}
