import { ApiNotice, Button, cx, LoadingState } from "../components/app-ui";
import { useLocale } from "../i18n-context";
import type { AuthUser } from "../lib/api";
import { EmployeeConversationPanel } from "./digital-employees/EmployeeConversationPanel";
import { EmployeeRail } from "./digital-employees/EmployeeRail";
import { EmployeeResultPanel } from "./digital-employees/EmployeeResultPanel";
import { EmployeeWorkspaceHeader } from "./digital-employees/EmployeeWorkspaceHeader";
import { useDigitalEmployeesController } from "./digital-employees/useDigitalEmployeesController";

export function DigitalEmployeesPage({
  isPrototype = false,
  user = null,
}: {
  isPrototype?: boolean;
  user?: AuthUser | null;
}) {
  const { t } = useLocale();
  const employee = useDigitalEmployeesController({ isPrototype, user });

  return (
    <section className="page employee-workspace employee-workspace-v2">
      {employee.loading && !employee.activeEmployees.length && (
        <LoadingState message={t("digitalEmployeesLoadingMessage")} lines={3} />
      )}
      {employee.loading && !!employee.activeEmployees.length && (
        <div className="refresh-indicator" role="status" aria-live="polite">
          <span className="refresh-spinner" aria-hidden="true" />
          {t("commonRefreshing")}
        </div>
      )}
      {employee.error && !employee.loading && (
        <ApiNotice
          title={t("digitalEmployeesUnavailableTitle")}
          message={employee.error}
          action={<Button onClick={employee.refetch}>{t("commonRetry")}</Button>}
        />
      )}
      {!employee.canUseAgents && (
        <ApiNotice title={t("digitalEmployeesNoAccessTitle")} message={t("digitalEmployeesNoAccessMessage")} />
      )}
      {employee.chat.actionError && (
        <ApiNotice title={t("digitalEmployeesActionErrorTitle")} message={employee.chat.actionError} />
      )}

      <div
        className={cx(
          "employee-layout",
          employee.agentsCollapsed && "agents-collapsed",
          employee.resultPanelOpen && employee.activeTaskSummary.hasResult && "result-open",
        )}
      >
        {!employee.agentsCollapsed && (
          <EmployeeRail
            activeCategory={employee.activeCategory}
            activeEmployeesCount={employee.activeEmployees.length}
            categoryCounts={employee.categoryCounts}
            loading={employee.loading}
            onActiveCategoryChange={employee.setActiveCategory}
            onSelectEmployee={employee.selectEmployee}
            onSelectSession={employee.chat.setActiveSession}
            selectedSessionId={employee.chat.activeSession?.id ?? null}
            selectedEmployee={employee.selectedEmployee}
            selectedEmployeeSessions={employee.selectedEmployeeSessions}
            visibleEmployees={employee.visibleEmployees}
          />
        )}

        <section className="employee-chat-panel">
          <EmployeeWorkspaceHeader
            agentsCollapsed={employee.agentsCollapsed}
            canChat={employee.canChat}
            canInspectEvidence={employee.canInspectEvidence}
            hasResult={employee.activeTaskSummary.hasResult}
            onNewTask={() => void employee.startConversation(employee.selectedEmployee)}
            onToggleAgents={() => employee.setAgentsCollapsed((collapsed) => !collapsed)}
            onToggleResultPanel={() => employee.setResultPanelOpen((open) => !open)}
            resultPanelOpen={employee.resultPanelOpen}
            selectedEmployee={employee.selectedEmployee}
          />

          <EmployeeConversationPanel
            canChat={employee.canChat}
            canInspectEvidence={employee.canInspectEvidence}
            draft={employee.draft}
            inputRef={employee.inputRef}
            messages={employee.chat.messages}
            onApplyStarter={employee.applyStarter}
            onDraftChange={employee.setDraft}
            onSend={() => void employee.send()}
            selectedEmployee={employee.selectedEmployee}
            sending={employee.chat.sending}
          />
        </section>

        {employee.resultPanelOpen && employee.activeTaskSummary.hasResult ? (
          <EmployeeResultPanel
            activeTaskSummary={employee.activeTaskSummary}
            canInspectEvidence={employee.canInspectEvidence}
            copiedResult={employee.copiedResult}
            latestAssistantMessage={employee.latestAssistantMessage}
            onClose={() => employee.setResultPanelOpen(false)}
            onCopyLatestAnswer={() => void employee.copyLatestAnswer()}
            onRefineLatestAnswer={employee.refineLatestAnswer}
          />
        ) : null}
      </div>
    </section>
  );
}
