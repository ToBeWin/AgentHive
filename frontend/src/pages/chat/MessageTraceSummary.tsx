import { AlertTriangle, DatabaseZap } from "lucide-react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { ChatMessageResponse } from "../../lib/api";
import { chatConfidenceLabelKey, chatMessageTraceSummary } from "./chatRunDetails";

const EMPTY_VALUE = "-";

export function MessageTraceSummary({ message }: { message: ChatMessageResponse }) {
  const { t } = useLocale();
  const summary = chatMessageTraceSummary(message);

  if (!summary) {
    return null;
  }

  return (
    <div className={cx("message-trace", summary.requiresReview && "needs-review")}>
      <div className="message-trace-header">
        <span>
          <DatabaseZap size={14} />
          {executionLabel(summary.execution, t)}
        </span>
        <StatusBadge
          label={t(chatConfidenceLabelKey(summary.confidence))}
          status={summary.requiresReview ? "warning" : summary.confidence}
        />
      </div>
      <div className="message-trace-grid">
        <span>{t("chatRunSourcesCount").replace("{{count}}", summary.sourceCount)}</span>
        <span>{t("chatRunMaxScore").replace("{{score}}", summary.maxScore)}</span>
      </div>
      {summary.firstSourceName !== EMPTY_VALUE && (
        <small>{t("chatRunTopSource").replace("{{source}}", summary.firstSourceName)}</small>
      )}
      {summary.requiresReview && (
        <small className="message-trace-review">
          <AlertTriangle size={13} />
          {t("chatRunHumanReviewRequired")}
          {summary.reviewReason !== EMPTY_VALUE ? ` · ${summary.reviewReason}` : ""}
        </small>
      )}
    </div>
  );
}

function executionLabel(execution: string, t: (key: string) => string) {
  if (execution === "agent_runtime") {
    return t("chatRunAgentRuntime");
  }
  if (execution === "streaming") {
    return t("chatRunStreaming");
  }
  if (execution === EMPTY_VALUE) {
    return t("chatRunTrace");
  }
  return execution.replace(/_/g, " ");
}
