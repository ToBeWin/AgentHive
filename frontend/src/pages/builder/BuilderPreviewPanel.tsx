import { Fragment } from "react";
import { useLocale } from "../../i18n-context";
import type { AgentBuilderConfigIssue, BuilderPreviewResponse } from "../../lib/api";
import { issueSeverityLabel } from "./builderUtils";

interface BuilderPreviewPanelProps {
  preview: BuilderPreviewResponse | null;
  issues: AgentBuilderConfigIssue[];
  validating: boolean;
  previewing: boolean;
}

const runtimeMetaLabels: Record<string, { zh: string; en: string }> = {
  model_key: { zh: "模型", en: "Model" },
  total_tokens: { zh: "总 Token 数", en: "Total Tokens" },
  prompt_tokens: { zh: "提示词 Token", en: "Prompt Tokens" },
  completion_tokens: { zh: "生成 Token", en: "Completion Tokens" },
  cost_usd: { zh: "费用", en: "Cost" },
  source: { zh: "来源", en: "Source" },
  preview: { zh: "预览模式", en: "Preview Mode" },
};

function formatRuntimeMetaValue(key: string, value: unknown, locale: "en-US" | "zh-CN"): string {
  const zh = locale === "zh-CN";
  if (value === null || value === undefined) return zh ? "无" : "—";
  if (key === "cost_usd" && typeof value === "number") {
    return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}`;
  }
  if ((key === "total_tokens" || key === "prompt_tokens" || key === "completion_tokens") && typeof value === "number") {
    return value.toLocaleString();
  }
  if (typeof value === "boolean") return zh ? (value ? "是" : "否") : value ? "Yes" : "No";
  if (typeof value === "number") return value.toLocaleString();
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export function BuilderPreviewPanel({ preview, issues, validating, previewing }: BuilderPreviewPanelProps) {
  const { locale, t } = useLocale();

  const errorCount = issues.filter((issue) => issue.severity === "error").length;
  const warningCount = issues.filter((issue) => issue.severity === "warning").length;

  const runtimeMetadata = preview?.rendered?.runtime_metadata;
  const metadataEntries =
    runtimeMetadata && typeof runtimeMetadata === "object"
      ? Object.entries(runtimeMetadata as Record<string, unknown>)
      : [];

  return (
    <div className="builder-preview-panel">
      <header>
        <h3>{t("builderPreviewTitle")}</h3>
        <p>{t("builderPreviewDesc")}</p>
      </header>

      {(validating || previewing) && (
        <div className="api-notice">
          <span>{t("builderPreviewLoading")}</span>
        </div>
      )}

      {issues.length > 0 && (
        <div className="builder-issues-list">
          <h4>
            {t("builderIssuesTitle")} · {errorCount} {locale === "zh-CN" ? "错误" : "errors"} · {warningCount}{" "}
            {locale === "zh-CN" ? "警告" : "warnings"}
          </h4>
          <ul>
            {issues.map((issue) => (
              <li
                key={`${issue.code}-${issue.field ?? ""}-${issue.message}`}
                className={`builder-issue builder-issue-${issue.severity}`}
                title={issue.field ? `${issue.code} · ${issue.field}` : issue.code}
              >
                <span className="builder-issue-severity">{issueSeverityLabel(issue.severity, locale)}</span>
                <span className="builder-issue-message">{issue.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {preview?.rendered && (
        <div className="builder-rendered-output">
          <h4>{t("builderRenderedTitle")}</h4>

          <section>
            <h5>{t("builderRenderedSystemPrompt")}</h5>
            <pre className="builder-prompt-preview">{preview.rendered.system_prompt}</pre>
          </section>

          <section>
            <h5>{t("builderRenderedUserPromptTemplate")}</h5>
            <code className="builder-template-preview">{preview.rendered.user_prompt_template}</code>
          </section>

          <section>
            <h5>{t("builderRenderedBehavior")}</h5>
            <dl className="builder-meta-grid">
              <dt>{t("builderRenderedResponseStyle")}</dt>
              <dd>{preview.rendered.response_style}</dd>
              <dt>{t("builderRenderedLanguage")}</dt>
              <dd>{preview.rendered.language}</dd>
              <dt>{t("builderRenderedConfidenceThreshold")}</dt>
              <dd>{preview.rendered.confidence_threshold ?? "—"}</dd>
              <dt>{t("builderRenderedBoundKnowledgeBases")}</dt>
              <dd>{preview.rendered.bound_knowledge_base_ids.length}</dd>
              <dt>{t("builderRenderedBoundMcpServers")}</dt>
              <dd>{preview.rendered.bound_mcp_server_keys.length}</dd>
            </dl>
          </section>

          {(preview.rendered.greeting_message ||
            preview.rendered.fallback_message ||
            preview.rendered.escalation_message) && (
            <section>
              <h5>{t("builderRenderedMessages")}</h5>
              {preview.rendered.greeting_message && (
                <div>
                  <strong>{t("builderRenderedGreeting")}</strong>
                  <p>{preview.rendered.greeting_message}</p>
                </div>
              )}
              {preview.rendered.fallback_message && (
                <div>
                  <strong>{t("builderRenderedFallback")}</strong>
                  <p>{preview.rendered.fallback_message}</p>
                </div>
              )}
              {preview.rendered.escalation_message && (
                <div>
                  <strong>{t("builderRenderedEscalation")}</strong>
                  <p>{preview.rendered.escalation_message}</p>
                </div>
              )}
            </section>
          )}

          {metadataEntries.length > 0 && (
            <section>
              <h5>{t("builderRenderedRuntimeMetadata")}</h5>
              <dl className="builder-meta-grid">
                {metadataEntries.map(([key, value]) => {
                  const label = runtimeMetaLabels[key]?.[locale === "zh-CN" ? "zh" : "en"] ?? key;
                  return (
                    <Fragment key={key}>
                      <dt>{label}</dt>
                      <dd>{formatRuntimeMetaValue(key, value, locale)}</dd>
                    </Fragment>
                  );
                })}
              </dl>
            </section>
          )}
        </div>
      )}

      {!preview && !validating && !previewing && issues.length === 0 && (
        <div className="builder-preview-empty">
          <p>{t("builderPreviewEmpty")}</p>
        </div>
      )}
    </div>
  );
}
