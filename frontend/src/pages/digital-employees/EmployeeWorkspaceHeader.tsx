import { MessageSquarePlus, PanelLeftClose, PanelLeftOpen, PanelRightOpen, Sparkles } from "lucide-react";
import { Button, cx } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import { agentDisplayDescription, agentDisplayName } from "../../lib/agentDisplay";
import type { WorkbenchAgentInstanceResponse } from "../../lib/api";
import { readinessReasonLabel } from "../../lib/readiness";

export function EmployeeWorkspaceHeader({
  agentsCollapsed,
  canChat,
  canInspectEvidence,
  hasResult,
  onNewTask,
  onToggleAgents,
  onToggleResultPanel,
  resultPanelOpen,
  selectedEmployee,
}: {
  agentsCollapsed: boolean;
  canChat: boolean;
  canInspectEvidence: boolean;
  hasResult: boolean;
  onNewTask: () => void;
  onToggleAgents: () => void;
  onToggleResultPanel: () => void;
  resultPanelOpen: boolean;
  selectedEmployee: WorkbenchAgentInstanceResponse | null;
}) {
  const { locale, t } = useLocale();
  const readable = selectedEmployee?.runnable !== false;
  const readinessLabel = readable ? t("agentReadinessReady") : t("agentReadinessNeedsConfiguration");
  const primaryReason = selectedEmployee?.readiness_reasons?.[0];

  return (
    <header className="employee-workspace-head employee-workspace-head-simple">
      <div className="employee-workspace-identity">
        <span className={cx("employee-avatar", "large", readable ? "ready" : "needs-configuration")}>
          <Sparkles size={24} />
        </span>
        <div>
          <span>{t("digitalEmployeesCurrentAgent")}</span>
          <strong>
            {selectedEmployee ? agentDisplayName(selectedEmployee, locale) : t("digitalEmployeesSelectOne")}
          </strong>
          <small>
            {selectedEmployee
              ? (agentDisplayDescription(selectedEmployee, locale) ?? t("digitalEmployeesReady"))
              : t("digitalEmployeesSelectOneDetail")}
          </small>
        </div>
      </div>

      {canInspectEvidence && (
        <div className="employee-workspace-meta">
          <span className={cx("employee-workspace-chip", readable ? "ready" : "warning")}>
            {readinessLabel}
            {!readable && primaryReason ? ` · ${readinessReasonLabel(primaryReason, t)}` : ""}
          </span>
          {selectedEmployee?.knowledge_enabled ? (
            <span className="employee-workspace-chip ready">
              {t("agentReadinessKnowledgeCount").replace("{{count}}", String(selectedEmployee.knowledge_base_count))}
            </span>
          ) : null}
        </div>
      )}

      <div className="employee-workspace-actions">
        <Button variant="ghost" onClick={onToggleAgents}>
          {agentsCollapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          {agentsCollapsed ? t("agentWorkbenchShowAgents") : t("agentWorkbenchHideAgents")}
        </Button>
        {!resultPanelOpen && hasResult ? (
          <Button variant="ghost" onClick={onToggleResultPanel}>
            <PanelRightOpen size={16} /> {t("digitalEmployeesShowResult")}
          </Button>
        ) : null}
        <Button disabled={!selectedEmployee || !canChat} onClick={onNewTask}>
          <MessageSquarePlus size={16} /> {t("digitalEmployeesNewChat")}
        </Button>
      </div>
    </header>
  );
}
