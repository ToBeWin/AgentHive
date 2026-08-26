import { useLocale } from "../../i18n-context";
import type { ModelUsageItem } from "../../lib/api";
import { formatCurrency, formatNumber } from "../../lib/formatters";

const MODEL_LABELS: Record<string, string> = {
  "gpt-4o-mini": "GPT-4o mini",
  "gpt-4o": "GPT-4o",
  "gpt-4-turbo": "GPT-4 Turbo",
  "gpt-3.5-turbo": "GPT-3.5",
  "claude-3-5-sonnet": "Claude 3.5 Sonnet",
  "claude-3-opus": "Claude 3 Opus",
  "claude-3-haiku": "Claude 3 Haiku",
  "gemini-1.5-pro": "Gemini 1.5 Pro",
  "gemini-1.5-flash": "Gemini 1.5 Flash",
};

function modelKeyToLabel(modelKey: string): string {
  if (MODEL_LABELS[modelKey]) {
    return MODEL_LABELS[modelKey];
  }
  if (modelKey.startsWith("qwen2.5-")) {
    return "通义千问 2.5";
  }
  if (modelKey.startsWith("deepseek-")) {
    return "DeepSeek";
  }
  const spaced = modelKey.replace(/-/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

function providerVisual(modelKey: string): { letter: string; color: string } {
  if (modelKey.startsWith("gpt")) {
    return { letter: "G", color: "#16a34a" };
  }
  if (modelKey.startsWith("claude")) {
    return { letter: "C", color: "#ea580c" };
  }
  if (modelKey.startsWith("gemini")) {
    return { letter: "G", color: "#2563eb" };
  }
  if (modelKey.startsWith("qwen")) {
    return { letter: "Q", color: "#6b7280" };
  }
  if (modelKey.startsWith("deepseek")) {
    return { letter: "D", color: "#6b7280" };
  }
  return { letter: modelKey.charAt(0).toUpperCase() || "?", color: "#6b7280" };
}

export function ModelPerformancePanel({
  modelUsage,
  onOpenModelCoverage,
}: {
  modelUsage: ModelUsageItem[];
  onOpenModelCoverage: () => void;
}) {
  const { locale, t } = useLocale();

  return (
    <div className="grid one lower">
      <section className="panel">
        <div className="panel-title">
          <h2>
            {t("overviewModelPerformance")} <span>{t("overviewModelPerformanceAlt")}</span>
          </h2>
          <button type="button" className="text-button" onClick={onOpenModelCoverage}>
            {t("overviewViewAll")}
          </button>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>{t("overviewProviderModel")}</th>
              <th>{t("overviewTokenColumn")}</th>
              <th>{t("overviewCostColumn")}</th>
              <th>{t("overviewRequestsColumn")}</th>
            </tr>
          </thead>
          <tbody>
            {modelUsage.map((row) => {
              const { letter, color } = providerVisual(row.model_key);
              return (
                <tr key={row.model_key}>
                  <td>
                    <span className="avatar small" style={{ backgroundColor: color }}>
                      {letter}
                    </span>
                    <span title={row.model_key}>{modelKeyToLabel(row.model_key)}</span>
                  </td>
                  <td>
                    {formatNumber(row.tokens, {}, locale)} {t("overviewTokenUnit")}
                  </td>
                  <td className="good">{formatCurrency(row.cost_usd)}</td>
                  <td>{formatNumber(row.requests, {}, locale)}</td>
                </tr>
              );
            })}
            {modelUsage.length === 0 && (
              <tr>
                <td colSpan={4}>{t("overviewNoModelUsage")}</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
