import { SendHorizontal, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import { Button, PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { KnowledgeBaseResponse, RetrievalTestResponse } from "../../lib/api";

interface KnowledgeRetrievalPanelProps {
  actionError: string | null;
  onRetrievalQueryChange: (value: string) => void;
  onRetrievalTest: () => void;
  onRetrievalTopKChange: (value: number) => void;
  retrievalQuery: string;
  retrievalResult: RetrievalTestResponse | null;
  retrievalTopK: number;
  selectedBase: KnowledgeBaseResponse | null;
  testing: boolean;
}

type KnowledgeRetrievalTab = "query" | "results";

export function KnowledgeRetrievalPanel({
  actionError,
  onRetrievalQueryChange,
  onRetrievalTest,
  onRetrievalTopKChange,
  retrievalQuery,
  retrievalResult,
  retrievalTopK,
  selectedBase,
  testing,
}: KnowledgeRetrievalPanelProps) {
  const { t } = useLocale();
  const [activeTab, setActiveTab] = useState<KnowledgeRetrievalTab>("query");

  return (
    <aside className="retrieval">
      <div className="list-title">
        <h2>{t("knowledgeRetrievalTitle")}</h2>
        <SlidersHorizontal size={20} />
      </div>
      <div className="nested-workspace retrieval-workspace">
        <PageTabs
          active={activeTab}
          onChange={setActiveTab}
          tabs={[
            { id: "query", label: t("knowledgeRetrievalTabQuery"), description: t("knowledgeRetrievalTabQueryDesc") },
            {
              id: "results",
              label: t("knowledgeRetrievalTabResults"),
              description: t("knowledgeRetrievalTabResultsDesc"),
            },
          ]}
        />
        {activeTab === "query" && (
          <div className="retrieval-section">
            <label>
              {t("knowledgeTestQuery")}
              <textarea
                placeholder={
                  selectedBase
                    ? t("knowledgeQueryPlaceholder").replace("{{name}}", selectedBase.name)
                    : t("knowledgeSelectBasePlaceholder")
                }
                value={retrievalQuery}
                onChange={(event) => onRetrievalQueryChange(event.target.value)}
              />
            </label>
            <label>
              {t("knowledgeTopK")}
              <input
                min={1}
                max={50}
                type="number"
                value={retrievalTopK}
                onChange={(event) => onRetrievalTopKChange(Number(event.target.value))}
              />
            </label>
            <Button
              onClick={() => {
                onRetrievalTest();
                setActiveTab("results");
              }}
              disabled={!selectedBase || testing || !retrievalQuery.trim()}
            >
              <SendHorizontal size={16} /> {testing ? t("knowledgeRunning") : t("knowledgeRunQuery")}
            </Button>
            {actionError && <div className="form-message error">{actionError}</div>}
            {!selectedBase && <div className="budget-empty-state">{t("knowledgeSelectBaseToRun")}</div>}
            {selectedBase && !retrievalResult && !testing && (
              <div className="budget-empty-state">{t("knowledgeRunQueryHelp")}</div>
            )}
          </div>
        )}
        {activeTab === "results" && (
          <div className="retrieval-section">
            {testing && <div className="budget-empty-state">{t("knowledgeRunning")}</div>}
            {retrievalResult && (
              <div className="retrieval-summary">
                <strong>
                  {t("knowledgeResultsCount").replace("{{count}}", String(retrievalResult.results.length))}
                </strong>
                <span>
                  {retrievalResult.engine} · {retrievalResult.elapsed_ms}ms
                </span>
              </div>
            )}
            {!retrievalResult && !testing && <div className="budget-empty-state">{t("knowledgeRunQueryHelp")}</div>}
            {retrievalResult?.results.length === 0 && (
              <div className="budget-empty-state">{t("knowledgeNoRetrievalResults")}</div>
            )}
            {retrievalResult?.results.map((result) => (
              <div className="retrieved" key={result.chunk_id}>
                <strong>{result.score === null ? t("knowledgeScoreUnavailable") : result.score.toFixed(2)}</strong>
                <code>{result.source_name ?? result.document_id ?? result.chunk_id}</code>
                <p>{result.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
