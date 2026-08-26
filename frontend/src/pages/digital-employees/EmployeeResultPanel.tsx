import { Copy, PanelRightClose, Sparkles } from "lucide-react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { ChatMessageResponse } from "../../lib/api";
import { latestAssistantRunDetails } from "../chat/chatRunDetails";
import { EmployeeMessageRuntimeMeta } from "./EmployeeMessageRuntimeMeta";
import type { ActiveEmployeeTaskSummary } from "./useDigitalEmployeesController";

export function EmployeeResultPanel({
  activeTaskSummary,
  canInspectEvidence,
  copiedResult,
  latestAssistantMessage,
  onClose,
  onCopyLatestAnswer,
  onRefineLatestAnswer,
}: {
  activeTaskSummary: ActiveEmployeeTaskSummary;
  canInspectEvidence: boolean;
  copiedResult: boolean;
  latestAssistantMessage: ChatMessageResponse | undefined;
  onClose: () => void;
  onCopyLatestAnswer: () => void;
  onRefineLatestAnswer: () => void;
}) {
  const { locale, t } = useLocale();
  const runDetails = latestAssistantRunDetails(latestAssistantMessage ? [latestAssistantMessage] : []);
  const hasResult = activeTaskSummary.hasResult;

  return (
    <aside className="employee-result-panel">
      <div className="employee-result-panel-head">
        <div>
          <span>{t("digitalEmployeesResultPanel")}</span>
          <strong>{hasResult ? t("digitalEmployeesResultReady") : t("digitalEmployeesNoResultYet")}</strong>
        </div>
        <button className="employee-result-panel-close" onClick={onClose} type="button">
          <PanelRightClose size={16} />
          <span>{t("digitalEmployeesHideResult")}</span>
        </button>
      </div>

      <div className="employee-result-panel-body">
        <section className="employee-result-status">
          <StatusBadge status={t(activeTaskSummary.statusKey)} />
          {activeTaskSummary.completedAt ? (
            <time dateTime={activeTaskSummary.completedAt}>{formatTime(activeTaskSummary.completedAt, locale)}</time>
          ) : null}
        </section>

        <article className={cx("employee-result-card", !hasResult && "empty")}>
          <p>{activeTaskSummary.latestAnswer || t("digitalEmployeesNoResultYet")}</p>
        </article>

        <div className="employee-result-actions">
          <button disabled={!hasResult} onClick={onCopyLatestAnswer} type="button">
            <Copy size={15} />
            {copiedResult ? t("digitalEmployeesCopiedResult") : t("digitalEmployeesCopyResult")}
          </button>
          <button disabled={!hasResult} onClick={onRefineLatestAnswer} type="button">
            <Sparkles size={15} />
            {t("digitalEmployeesRefineResult")}
          </button>
        </div>

        {runDetails.sources.length > 0 ? (
          <section className="employee-result-sources">
            <strong>{t("digitalEmployeesKnowledgeSources")}</strong>
            <ul>
              {runDetails.sources.map((source) => (
                <li key={source.id}>
                  <span>{source.sourceName}</span>
                  <small>{source.score !== "-" ? `${t("digitalEmployeesSourceScore")}: ${source.score}` : ""}</small>
                  <p>{source.text}</p>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {canInspectEvidence && latestAssistantMessage ? (
          <section className="employee-result-evidence">
            <strong>{t("digitalEmployeesRuntimeEvidence")}</strong>
            <EmployeeMessageRuntimeMeta message={latestAssistantMessage} />
          </section>
        ) : null}
      </div>
    </aside>
  );
}

function formatTime(value: string, locale: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
  }).format(date);
}
