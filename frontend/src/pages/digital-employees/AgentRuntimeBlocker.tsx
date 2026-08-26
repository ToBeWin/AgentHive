import { AlertTriangle, Route } from "lucide-react";
import { Button } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { WorkbenchAgentInstanceResponse } from "../../lib/api";
import {
  readinessReasonAdminAction,
  readinessReasonEmployeeImpact,
  readinessReasonLabel,
  uniqueReadinessReasons,
} from "../../lib/readiness";

interface AgentRuntimeBlockerProps {
  canInspectEvidence: boolean;
  onShowRunEvidence: () => void;
  selectedEmployee: WorkbenchAgentInstanceResponse;
}

export function AgentRuntimeBlocker({
  canInspectEvidence,
  onShowRunEvidence,
  selectedEmployee,
}: AgentRuntimeBlockerProps) {
  const { t } = useLocale();
  const reasons = uniqueReadinessReasons(selectedEmployee.readiness_reasons ?? []);
  const visibleReasons = reasons.length ? reasons : ["unknown"];

  return (
    <section className="employee-runtime-blocker" aria-live="polite">
      <div className="employee-runtime-blocker-summary">
        <AlertTriangle size={18} />
        <div>
          <strong>{t("digitalEmployeesAgentNotRunnableTitle")}</strong>
          <p>{t("digitalEmployeesAgentNotRunnableMessage")}</p>
          <ul className="employee-runtime-impact-list" aria-label={t("digitalEmployeesAgentNotRunnableImpact")}>
            {visibleReasons.map((reason) => (
              <li key={reason}>{readinessReasonEmployeeImpact(reason, t)}</li>
            ))}
          </ul>
        </div>
      </div>

      {canInspectEvidence && (
        <div className="employee-runtime-diagnostics">
          <div className="employee-runtime-diagnostics-head">
            <span>{t("digitalEmployeesAgentNotRunnableOperatorHint")}</span>
            <Button onClick={onShowRunEvidence} variant="ghost">
              <Route size={15} /> {t("digitalEmployeesInspectSetupEvidence")}
            </Button>
          </div>
          <div className="employee-runtime-repair-list">
            {visibleReasons.map((reason) => (
              <div key={reason}>
                <strong>{readinessReasonLabel(reason, t)}</strong>
                <small>{readinessReasonAdminAction(reason, t)}</small>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
