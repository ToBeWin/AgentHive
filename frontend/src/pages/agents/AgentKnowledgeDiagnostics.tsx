import { DatabaseZap } from "lucide-react";
import { useLocale } from "../../i18n-context";
import type { AgentRunResponse } from "../../lib/api";

type KnowledgeDiagnostics = {
  enabled?: boolean;
  reason?: string;
  source_count?: number;
  top_k?: number;
  confidence_level?: string;
  max_score?: number | null;
  min_score?: number | null;
  requires_human_review?: boolean;
  review_reason?: string;
  guardrail?: {
    mode?: string;
    triggered?: boolean;
    skipped_model_call?: boolean;
    reason?: string;
  };
  per_base?: Array<{
    knowledge_base_id?: string;
    knowledge_base_name?: string;
    knowledge_base_visibility?: string;
    engine?: string;
    source_count?: number;
    elapsed_ms?: number;
  }>;
};

export function AgentKnowledgeDiagnostics({ response }: { response: AgentRunResponse }) {
  const { t } = useLocale();
  const diagnostics = parseKnowledgeDiagnostics(response.metadata.knowledge);
  if (!diagnostics?.enabled) {
    return (
      <div className="agent-knowledge-diagnostics muted">
        <DatabaseZap size={16} />
        <span>{t("agentsKnowledgeNotEnabled")}</span>
      </div>
    );
  }
  const requiresReview = diagnostics.requires_human_review === true;
  const confidenceLevel = String(diagnostics.confidence_level ?? "unknown");
  const maxScore = typeof diagnostics.max_score === "number" ? diagnostics.max_score.toFixed(2) : "-";
  const guardrail = diagnostics.guardrail;
  const guardrailTriggered = guardrail?.triggered === true;

  return (
    <div className={requiresReview ? "agent-knowledge-diagnostics needs-review" : "agent-knowledge-diagnostics"}>
      <div className="agent-knowledge-summary">
        <DatabaseZap size={16} />
        <div>
          <strong>
            {t("agentsKnowledgeSummary")
              .replace("{{count}}", String(diagnostics.source_count ?? 0))
              .replace("{{topK}}", String(diagnostics.top_k ?? "-"))}
          </strong>
          <span>{String(diagnostics.reason ?? t("agentsRetrievalChecked"))}</span>
        </div>
      </div>
      <div className="agent-knowledge-confidence">
        <div>
          <span>{t("agentsKnowledgeConfidence")}</span>
          <strong>{t(confidenceLabelKey(confidenceLevel))}</strong>
          <small>{t("agentsKnowledgeMaxScore").replace("{{score}}", maxScore)}</small>
        </div>
        <div>
          <span>{t("agentsHumanReview")}</span>
          <strong>{requiresReview ? t("agentsRequired") : t("agentsNotRequired")}</strong>
          <small>{String(diagnostics.review_reason ?? t("agentsRetrievalChecked"))}</small>
        </div>
        <div>
          <span>{t("agentsKnowledgeGuardrail")}</span>
          <strong>{guardrailTriggered ? t("agentsTriggered") : t("agentsNotTriggered")}</strong>
          <small>
            {t("agentsKnowledgeGuardrailMode").replace("{{mode}}", String(guardrail?.mode ?? "strict"))}
            {guardrail?.skipped_model_call ? ` · ${t("agentsModelCallSkipped")}` : ""}
          </small>
        </div>
      </div>
      {diagnostics.per_base?.length ? (
        <div className="agent-knowledge-base-list">
          {diagnostics.per_base.map((item) => (
            <div key={`${String(item.knowledge_base_id ?? "kb")}-${String(item.engine ?? "engine")}`}>
              <strong>{String(item.knowledge_base_name ?? shortId(item.knowledge_base_id))}</strong>
              <span>
                {shortId(item.knowledge_base_id)} · {String(item.knowledge_base_visibility ?? "-")} ·{" "}
                {String(item.engine ?? "-")} ·{" "}
                {t("agentsSourcesCount").replace("{{count}}", String(item.source_count ?? 0))} ·{" "}
                {String(item.elapsed_ms ?? 0)}ms
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function parseKnowledgeDiagnostics(value: unknown): KnowledgeDiagnostics | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  return value as KnowledgeDiagnostics;
}

function shortId(value: string | undefined): string {
  if (!value) {
    return "-";
  }
  if (value.length <= 12) {
    return value;
  }
  return `${value.slice(0, 8)}...${value.slice(-4)}`;
}

function confidenceLabelKey(level: string): string {
  const keys: Record<string, string> = {
    high: "agentsConfidenceHigh",
    low: "agentsConfidenceLow",
    medium: "agentsConfidenceMedium",
    no_match: "agentsConfidenceNoMatch",
    unscored: "agentsConfidenceUnscored",
  };
  return keys[level] ?? "agentsConfidenceUnknown";
}
