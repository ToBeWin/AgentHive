import { ApiNotice, cx, PageTabs } from "../../components/app-ui";
import { Markdown } from "../../components/Markdown";
import { useLocale } from "../../i18n-context";
import type { AgentInstanceResponse, AgentRunResponse } from "../../lib/api";
import { formatCurrency } from "../../lib/formatters";
import { readinessReasonLabels } from "../../lib/readiness";
import type { AgentRuntimeTestTab } from "./agentRuntimeTypes";

interface AgentRuntimeTestPanelProps {
  activeTestTab: AgentRuntimeTestTab;
  error: string | null;
  input: string;
  inputError?: string | null;
  onInputChange: (value: string) => void;
  onTestTabChange: (tab: AgentRuntimeTestTab) => void;
  response: AgentRunResponse | null;
  selectedInstance: AgentInstanceResponse | null;
}

export function AgentRuntimeTestPanel({
  activeTestTab,
  error,
  input,
  inputError,
  onInputChange,
  onTestTabChange,
  response,
  selectedInstance,
}: AgentRuntimeTestPanelProps) {
  const { t } = useLocale();

  return (
    <div className="nested-workspace agent-runtime-test-workspace">
      <PageTabs
        active={activeTestTab}
        onChange={onTestTabChange}
        tabs={[
          { id: "input", label: t("agentsRuntimeTestInputTab"), description: t("agentsRuntimeTestInputTabDesc") },
          {
            id: "result",
            label: t("agentsRuntimeTestResultTab"),
            description: t("agentsRuntimeTestResultTabDesc"),
          },
        ]}
      />
      {activeTestTab === "input" && (
        <>
          <h3>{t("agentsRunTest")}</h3>
          <label>
            {t("agentsCustomerInput")}
            <textarea
              value={input}
              onChange={(event) => onInputChange(event.target.value)}
              className={cx(inputError ? "form-input-error" : undefined)}
              aria-invalid={inputError ? true : undefined}
            />
            {inputError && <span className="form-field-error">{inputError}</span>}
          </label>
          {selectedInstance?.runnable === false && (
            <ApiNotice
              title={t("agentsRuntimeReadinessWarning")}
              message={readinessReasonLabels(selectedInstance.readiness_reasons ?? [], t).join(" / ")}
            />
          )}
          {error && <ApiNotice title={t("agentsRunFailed")} message={error} />}
          <div className="field-block">
            <span>{t("agentsRuntimeTestNext")}</span>
            <p>{t("agentsRuntimeTestNextDetail")}</p>
          </div>
        </>
      )}
      {activeTestTab === "result" &&
        (response ? (
          <div className="prompt-box">
            <div>
              <h3>{t("agentsAnswer")}</h3>
              <code>{response.model_key}</code>
            </div>
            <Markdown>{response.answer}</Markdown>
            <small>
              {response.usage.total_tokens} {t("agentsTokens")} · {formatCurrency(response.usage.cost_usd)} ·{" "}
              {String(response.metadata.license_gate ?? t("agentsNoDiagnostic"))}
            </small>
          </div>
        ) : (
          <ApiNotice title={t("agentsRuntimeResultEmptyTitle")} message={t("agentsRuntimeResultEmptyMessage")} />
        ))}
    </div>
  );
}
