import { ApiNotice } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { AgentRunResponse } from "../../lib/api";
import { AgentKnowledgeDiagnostics } from "./AgentKnowledgeDiagnostics";
import { AgentRunDiagnostics } from "./AgentRunDiagnostics";
import { sourceKey, sourceLabel } from "./agentUtils";

export function AgentRuntimeEvidencePanel({ response }: { response: AgentRunResponse | null }) {
  const { t } = useLocale();

  return response ? (
    <div className="prompt-box">
      <div>
        <h3>{t("agentsRuntimeEvidenceTitle")}</h3>
        <code>{response.request_id}</code>
      </div>
      <AgentRunDiagnostics response={response} />
      <AgentKnowledgeDiagnostics response={response} />
      {response.sources.length > 0 && (
        <div className="source-list">
          <strong>{t("agentsSources")}</strong>
          {response.sources.map((source) => (
            <small key={sourceKey(source)}>
              {sourceLabel(source)} · {t("agentsScore")} {String(source.score ?? "-")}
            </small>
          ))}
        </div>
      )}
    </div>
  ) : (
    <ApiNotice title={t("agentsRuntimeEvidenceEmptyTitle")} message={t("agentsRuntimeEvidenceEmptyMessage")} />
  );
}
