import { ChevronDown, ChevronRight } from "lucide-react";
import { type ReactNode, useState } from "react";
import { CharCounter, FieldLabel } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { AgentBuilderConfigIssue, BuilderResponseStyle, BuilderSupportedLanguage } from "../../lib/api";
import {
  type AgentKnowledgeBaseOption,
  type AgentMcpServerOption,
  type AgentModelDeploymentOption,
  type BuilderFormState,
  issueSeverityLabel,
} from "./builderUtils";

interface BuilderFormProps {
  canWrite: boolean;
  form: BuilderFormState;
  knowledgeBases: AgentKnowledgeBaseOption[];
  mcpServers: AgentMcpServerOption[];
  modelDeployments: AgentModelDeploymentOption[];
  onFieldChange: <K extends keyof BuilderFormState>(field: K, value: BuilderFormState[K]) => void;
  issues: AgentBuilderConfigIssue[];
  /** Real-time hints derived from form state (e.g. "escalation_message required"). */
  runtimeHints?: Array<{ field: string; message: string }>;
}

function FormSection({
  children,
  collapsible = false,
  defaultOpen = true,
  description,
  step,
  title,
}: {
  children: ReactNode;
  collapsible?: boolean;
  defaultOpen?: boolean;
  description: string;
  step: string;
  title: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const head = (
    <div className="agent-instance-form-section-head">
      <span className="step-badge">{step}</span>
      <div>
        <strong>{title}</strong>
        <small>{description}</small>
      </div>
    </div>
  );
  if (!collapsible) {
    return (
      <section className="agent-instance-form-section">
        {head}
        <div className="agent-instance-form-section-body budget-form-grid agent-instance-form">{children}</div>
      </section>
    );
  }
  const ToggleIcon = open ? ChevronDown : ChevronRight;
  return (
    <details
      className="agent-instance-form-section collapsible"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        {head}
        <ToggleIcon size={16} aria-hidden />
      </summary>
      <div className="agent-instance-form-section-body budget-form-grid agent-instance-form">{children}</div>
    </details>
  );
}

function FieldIssues({
  issues,
  hints,
  field,
  locale,
}: {
  issues: AgentBuilderConfigIssue[];
  hints: Array<{ field: string; message: string }>;
  field: string;
  locale: "en-US" | "zh-CN";
}) {
  const fieldIssues = issues.filter((issue) => issue.field === field);
  const fieldHints = hints.filter((hint) => hint.field === field);
  if (fieldIssues.length === 0 && fieldHints.length === 0) return null;
  return (
    <>
      {fieldIssues.map((issue) => (
        <small key={`issue-${issue.code}-${issue.field ?? ""}-${issue.message}`} className="form-error">
          {issueSeverityLabel(issue.severity, locale)}: {issue.message}
        </small>
      ))}
      {fieldHints.map((hint) => (
        <small key={`hint-${field}-${hint.message}`} className="form-error">
          {locale === "zh-CN" ? "提示" : "Hint"}: {hint.message}
        </small>
      ))}
    </>
  );
}

export function BuilderForm({
  canWrite,
  form,
  knowledgeBases,
  mcpServers,
  modelDeployments,
  onFieldChange,
  issues,
  runtimeHints = [],
}: BuilderFormProps) {
  const { locale, t } = useLocale();

  const toggleKnowledgeBase = (id: string) => {
    const next = form.knowledge_base_ids.includes(id)
      ? form.knowledge_base_ids.filter((kbId) => kbId !== id)
      : [...form.knowledge_base_ids, id];
    onFieldChange("knowledge_base_ids", next);
  };

  const toggleMcpServer = (serverKey: string) => {
    const next = form.mcp_server_keys.includes(serverKey)
      ? form.mcp_server_keys.filter((key) => key !== serverKey)
      : [...form.mcp_server_keys, serverKey];
    onFieldChange("mcp_server_keys", next);
  };

  const toggleFallbackDeployment = (id: string) => {
    const next = form.fallback_deployment_ids.includes(id)
      ? form.fallback_deployment_ids.filter((depId) => depId !== id)
      : [...form.fallback_deployment_ids, id];
    onFieldChange("fallback_deployment_ids", next);
  };

  return (
    <div className="agent-instance-form-shell">
      <FormSection
        collapsible
        defaultOpen
        description={t("builderFormIdentityDesc")}
        step="1"
        title={t("builderFormIdentityTitle")}
      >
        <div>
          <FieldLabel required htmlFor="builder-form-name">
            {t("builderFormName")}
          </FieldLabel>
          <input
            id="builder-form-name"
            disabled={!canWrite}
            value={form.name}
            maxLength={120}
            onChange={(event) => onFieldChange("name", event.target.value)}
          />
          <FieldIssues issues={issues} hints={runtimeHints} field="name" locale={locale} />
        </div>
        <label>
          {t("builderFormDescription")}
          <input
            disabled={!canWrite}
            value={form.description}
            maxLength={500}
            onChange={(event) => onFieldChange("description", event.target.value)}
          />
          <FieldIssues issues={issues} hints={runtimeHints} field="description" locale={locale} />
        </label>
        <label>
          {t("builderFormAvatarUrl")}
          <input
            disabled={!canWrite}
            value={form.avatar_url}
            maxLength={500}
            onChange={(event) => onFieldChange("avatar_url", event.target.value)}
          />
          <FieldIssues issues={issues} hints={runtimeHints} field="avatar_url" locale={locale} />
        </label>
      </FormSection>

      <FormSection
        collapsible
        defaultOpen={false}
        description={t("builderFormRoutingDesc")}
        step="2"
        title={t("builderFormRoutingTitle")}
      >
        <div>
          <FieldLabel required htmlFor="builder-form-deployment">
            {t("builderFormDeployment")}
          </FieldLabel>
          <select
            id="builder-form-deployment"
            disabled={!canWrite}
            value={form.deployment_id}
            onChange={(event) => onFieldChange("deployment_id", event.target.value)}
          >
            <option value="">{t("builderFormDeploymentNone")}</option>
            {modelDeployments.map((dep) => (
              <option key={dep.id} value={dep.id}>
                {dep.label}
              </option>
            ))}
          </select>
          <small className="form-hint">{t("builderFormDeploymentHint")}</small>
          <FieldIssues issues={issues} hints={runtimeHints} field="deployment_id" locale={locale} />
        </div>
        <div className="agent-instance-form-wide">
          <details className="agent-instance-optional-field">
            <summary>{t("builderFormAdvancedRoutingTitle")}</summary>
            <label>
              {t("builderFormModelKey")}
              <input
                disabled={!canWrite}
                value={form.model_key}
                maxLength={120}
                onChange={(event) => onFieldChange("model_key", event.target.value)}
              />
              <FieldIssues issues={issues} hints={runtimeHints} field="model_key" locale={locale} />
            </label>
            <label>
              {t("builderFormRoutingKey")}
              <input
                disabled={!canWrite}
                value={form.routing_key}
                maxLength={120}
                onChange={(event) => onFieldChange("routing_key", event.target.value)}
              />
              <FieldIssues issues={issues} hints={runtimeHints} field="routing_key" locale={locale} />
            </label>
          </details>
        </div>
        <div className="agent-instance-form-wide">
          <span className="form-field-label">{t("builderFormFallbackDeployments")}</span>
          <div className="agent-instance-form-checkbox-group">
            {modelDeployments.length === 0 && <span className="form-hint">{t("builderFormNoDeployments")}</span>}
            {modelDeployments
              .filter((dep) => dep.id !== form.deployment_id)
              .map((dep) => (
                <label key={dep.id} className="checkbox-line">
                  <input
                    disabled={!canWrite}
                    type="checkbox"
                    checked={form.fallback_deployment_ids.includes(dep.id)}
                    onChange={() => toggleFallbackDeployment(dep.id)}
                  />
                  <span>{dep.label}</span>
                </label>
              ))}
          </div>
          <FieldIssues issues={issues} hints={runtimeHints} field="fallback_deployment_ids" locale={locale} />
        </div>
      </FormSection>

      <FormSection
        collapsible
        defaultOpen={false}
        description={t("builderFormGenerationDesc")}
        step="3"
        title={t("builderFormGenerationTitle")}
      >
        <label>
          {t("builderFormTemperature")}
          <input
            disabled={!canWrite}
            type="number"
            min={0}
            max={2}
            step={0.1}
            placeholder={t("builderFormTemperaturePlaceholder")}
            value={form.temperature}
            onChange={(event) => onFieldChange("temperature", event.target.value)}
          />
          <small className="form-hint">{t("builderFormTemperatureHint")}</small>
          <FieldIssues issues={issues} hints={runtimeHints} field="temperature" locale={locale} />
        </label>
        <label>
          {t("builderFormMaxTokens")}
          <input
            disabled={!canWrite}
            type="number"
            min={1}
            max={8192}
            step={1}
            placeholder={t("builderFormMaxTokensPlaceholder")}
            value={form.max_tokens}
            onChange={(event) => onFieldChange("max_tokens", event.target.value)}
          />
          <small className="form-hint">{t("builderFormMaxTokensHint")}</small>
          <FieldIssues issues={issues} hints={runtimeHints} field="max_tokens" locale={locale} />
        </label>
        <label>
          {t("builderFormMaxCostPerRequest")}
          <input
            disabled={!canWrite}
            type="number"
            min={0}
            step={0.001}
            value={form.max_cost_per_request}
            onChange={(event) => onFieldChange("max_cost_per_request", event.target.value)}
          />
          <FieldIssues issues={issues} hints={runtimeHints} field="max_cost_per_request" locale={locale} />
        </label>
      </FormSection>

      <FormSection
        collapsible
        defaultOpen={false}
        description={t("builderFormPersonaDesc")}
        step="4"
        title={t("builderFormPersonaTitle")}
      >
        <div className="agent-instance-form-wide">
          <FieldLabel required htmlFor="builder-form-system-prompt">
            {t("builderFormSystemPrompt")}
          </FieldLabel>
          <textarea
            id="builder-form-system-prompt"
            disabled={!canWrite}
            rows={8}
            placeholder={t("builderFormSystemPromptPlaceholder")}
            value={form.system_prompt}
            maxLength={8000}
            onChange={(event) => onFieldChange("system_prompt", event.target.value)}
          />
          <CharCounter value={form.system_prompt.length} max={8000} />
          <small className="form-hint">{t("builderFormSystemPromptHint")}</small>
          <FieldIssues issues={issues} hints={runtimeHints} field="system_prompt" locale={locale} />
        </div>
        <label>
          {t("builderFormResponseStyle")}
          <select
            disabled={!canWrite}
            value={form.response_style}
            onChange={(event) => onFieldChange("response_style", event.target.value as BuilderResponseStyle)}
          >
            <option value="formal">{t("builderFormResponseStyleFormal")}</option>
            <option value="friendly">{t("builderFormResponseStyleFriendly")}</option>
            <option value="concise">{t("builderFormResponseStyleConcise")}</option>
          </select>
          <FieldIssues issues={issues} hints={runtimeHints} field="response_style" locale={locale} />
        </label>
        <label>
          {t("builderFormLanguage")}
          <select
            disabled={!canWrite}
            value={form.language}
            onChange={(event) => onFieldChange("language", event.target.value as BuilderSupportedLanguage)}
          >
            <option value="auto">{t("builderFormLanguageAuto")}</option>
            <option value="zh">{t("builderFormLanguageZh")}</option>
            <option value="en">{t("builderFormLanguageEn")}</option>
          </select>
          <FieldIssues issues={issues} hints={runtimeHints} field="language" locale={locale} />
        </label>
      </FormSection>

      <FormSection
        collapsible
        defaultOpen={false}
        description={t("builderFormResourcesDesc")}
        step="5"
        title={t("builderFormResourcesTitle")}
      >
        <div className="agent-instance-form-wide">
          <span className="form-field-label">{t("builderFormKnowledgeBases")}</span>
          <div className="agent-instance-form-checkbox-group">
            {knowledgeBases.length === 0 && <span className="form-hint">{t("builderFormNoKnowledgeBases")}</span>}
            {knowledgeBases.map((kb) => (
              <label key={kb.id} className="checkbox-line">
                <input
                  disabled={!canWrite}
                  type="checkbox"
                  checked={form.knowledge_base_ids.includes(kb.id)}
                  onChange={() => toggleKnowledgeBase(kb.id)}
                />
                <span title={locale === "zh-CN" ? `检索引擎: ${kb.rag_engine}` : `Retrieval engine: ${kb.rag_engine}`}>
                  {kb.name}
                </span>
              </label>
            ))}
          </div>
          <FieldIssues issues={issues} hints={runtimeHints} field="knowledge_base_ids" locale={locale} />
        </div>
        <div className="agent-instance-form-wide">
          <span className="form-field-label">{t("builderFormMcpServers")}</span>
          <div className="agent-instance-form-checkbox-group">
            {mcpServers.length === 0 && <span className="form-hint">{t("builderFormNoMcpServers")}</span>}
            {mcpServers.map((server) => (
              <label key={server.id} className="checkbox-line">
                <input
                  disabled={!canWrite}
                  type="checkbox"
                  checked={form.mcp_server_keys.includes(server.server_key)}
                  onChange={() => toggleMcpServer(server.server_key)}
                />
                <span
                  title={
                    locale === "zh-CN"
                      ? `Key: ${server.server_key} · 状态: ${server.status}`
                      : `Key: ${server.server_key} · Status: ${server.status}`
                  }
                >
                  {server.name}
                  <span
                    className={`mcp-status-dot mcp-status-${server.status}`}
                    role="img"
                    aria-label={server.status}
                  />
                </span>
              </label>
            ))}
          </div>
          <FieldIssues issues={issues} hints={runtimeHints} field="mcp_server_keys" locale={locale} />
        </div>
      </FormSection>

      <FormSection
        collapsible
        defaultOpen={false}
        description={t("builderFormSafetyDesc")}
        step="6"
        title={t("builderFormSafetyTitle")}
      >
        <label>
          {t("builderFormConfidenceThreshold")}
          <input
            disabled={!canWrite}
            type="number"
            min={0}
            max={1}
            step={0.05}
            placeholder={t("builderFormConfidenceThresholdPlaceholder")}
            value={form.confidence_threshold}
            onChange={(event) => onFieldChange("confidence_threshold", event.target.value)}
          />
          <small className="form-hint">{t("builderFormConfidenceThresholdHint")}</small>
          <FieldIssues issues={issues} hints={runtimeHints} field="confidence_threshold" locale={locale} />
        </label>
        <label className="agent-instance-form-wide">
          {t("builderFormEscalationMessage")}
          <textarea
            disabled={!canWrite}
            rows={2}
            value={form.escalation_message}
            maxLength={1000}
            onChange={(event) => onFieldChange("escalation_message", event.target.value)}
          />
          <CharCounter value={form.escalation_message.length} max={1000} />
          <small className="form-hint">{t("builderFormEscalationMessageHint")}</small>
          <FieldIssues issues={issues} hints={runtimeHints} field="escalation_message" locale={locale} />
        </label>
        <label className="agent-instance-form-wide">
          {t("builderFormGreetingMessage")}
          <textarea
            disabled={!canWrite}
            rows={2}
            value={form.greeting_message}
            maxLength={2000}
            onChange={(event) => onFieldChange("greeting_message", event.target.value)}
          />
          <CharCounter value={form.greeting_message.length} max={2000} />
          <FieldIssues issues={issues} hints={runtimeHints} field="greeting_message" locale={locale} />
        </label>
        <label className="agent-instance-form-wide">
          {t("builderFormFallbackMessage")}
          <textarea
            disabled={!canWrite}
            rows={2}
            value={form.fallback_message}
            maxLength={2000}
            onChange={(event) => onFieldChange("fallback_message", event.target.value)}
          />
          <CharCounter value={form.fallback_message.length} max={2000} />
          <FieldIssues issues={issues} hints={runtimeHints} field="fallback_message" locale={locale} />
        </label>
      </FormSection>
    </div>
  );
}
