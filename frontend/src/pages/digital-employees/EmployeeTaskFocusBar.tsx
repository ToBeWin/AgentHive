import { useLocale } from "../../i18n-context";

export type EmployeeTaskTab = "conversation" | "result" | "actions" | "context";

interface EmployeeTaskFocusBarProps {
  activeTab: EmployeeTaskTab;
  hasResult: boolean;
  hasUserTask: boolean;
  onOpenActions: () => void;
  onOpenConversation: () => void;
  onOpenContext: () => void;
  onOpenResult: () => void;
  selectedWorkflowLabel: string;
  sending: boolean;
}

export function EmployeeTaskFocusBar({
  activeTab,
  hasResult,
  hasUserTask,
  onOpenActions,
  onOpenConversation,
  onOpenContext,
  onOpenResult,
  selectedWorkflowLabel,
  sending,
}: EmployeeTaskFocusBarProps) {
  const { t } = useLocale();
  const focus = taskFocusCopy({
    activeTab,
    hasResult,
    hasUserTask,
    onOpenActions,
    onOpenConversation,
    onOpenContext,
    onOpenResult,
    sending,
    t,
  });
  return (
    <section className="employee-task-focus" aria-label={t("digitalEmployeesFocusModeLabel")}>
      <div>
        <span>{t("digitalEmployeesFocusModeLabel")}</span>
        <strong>{focus.title}</strong>
        <p>{focus.description}</p>
      </div>
      <dl>
        <div>
          <dt>{t("digitalEmployeesFocusStatus")}</dt>
          <dd>{focus.status}</dd>
        </div>
        <div>
          <dt>{t("digitalEmployeesFocusSelectedWorkflow")}</dt>
          <dd>{selectedWorkflowLabel}</dd>
        </div>
      </dl>
      <button type="button" onClick={focus.action}>
        {focus.actionLabel}
      </button>
    </section>
  );
}

function taskFocusCopy({
  activeTab,
  hasResult,
  hasUserTask,
  onOpenActions,
  onOpenConversation,
  onOpenContext,
  onOpenResult,
  sending,
  t,
}: {
  activeTab: EmployeeTaskTab;
  hasResult: boolean;
  hasUserTask: boolean;
  onOpenActions: () => void;
  onOpenConversation: () => void;
  onOpenContext: () => void;
  onOpenResult: () => void;
  sending: boolean;
  t: (key: string) => string;
}) {
  if (activeTab === "actions") {
    return {
      action: onOpenConversation,
      actionLabel: t("digitalEmployeesFocusActionsAction"),
      description: t("digitalEmployeesFocusActionsDesc"),
      status: hasUserTask ? t("digitalEmployeesProgressTaskSent") : t("digitalEmployeesProgressDescribeTask"),
      title: t("digitalEmployeesFocusActionsTitle"),
    };
  }
  if (activeTab === "context") {
    return {
      action: onOpenConversation,
      actionLabel: t("digitalEmployeesFocusContextAction"),
      description: t("digitalEmployeesFocusContextDesc"),
      status: hasUserTask ? t("digitalEmployeesProgressTaskSent") : t("digitalEmployeesProgressDescribeTask"),
      title: t("digitalEmployeesFocusContextTitle"),
    };
  }
  if (activeTab === "result") {
    return {
      action: onOpenConversation,
      actionLabel: t("digitalEmployeesFocusResultAction"),
      description: hasResult ? t("digitalEmployeesFocusResultDesc") : t("digitalEmployeesFocusResultEmptyDesc"),
      status: hasResult ? t("digitalEmployeesResultReady") : t("digitalEmployeesNoResultYet"),
      title: t("digitalEmployeesFocusResultTitle"),
    };
  }
  return {
    action: hasResult ? onOpenResult : hasUserTask ? onOpenContext : onOpenActions,
    actionLabel: hasResult
      ? t("digitalEmployeesFocusConversationResultAction")
      : hasUserTask
        ? t("digitalEmployeesFocusConversationContextAction")
        : t("digitalEmployeesFocusConversationAction"),
    description: t("digitalEmployeesFocusConversationDesc"),
    status: sending
      ? t("digitalEmployeesProgressGenerating")
      : hasUserTask
        ? t("digitalEmployeesProgressTaskSent")
        : t("digitalEmployeesProgressDescribeTask"),
    title: t("digitalEmployeesFocusConversationTitle"),
  };
}
