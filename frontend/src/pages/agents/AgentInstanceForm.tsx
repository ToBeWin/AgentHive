import type { ReactNode } from "react";
import { FieldLabel } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import { agentDisplayName } from "../../lib/agentDisplay";
import type { AgentCatalogEntryResponse } from "../../lib/api";
import { AgentKnowledgeBindingPicker } from "./AgentKnowledgeBindingPicker";
import type { AgentInstanceFormState, AgentKnowledgeBaseOption } from "./agentInstanceUtils";

export function AgentInstanceForm({
  canWrite,
  catalog,
  form,
  knowledgeBases,
  onAgentChange,
  onFieldChange,
}: {
  canWrite: boolean;
  catalog: AgentCatalogEntryResponse[];
  form: AgentInstanceFormState;
  knowledgeBases: AgentKnowledgeBaseOption[];
  onAgentChange: (agentKey: string) => void;
  onFieldChange: <K extends keyof AgentInstanceFormState>(field: K, value: AgentInstanceFormState[K]) => void;
}) {
  const { locale, t } = useLocale();
  const routingHasOverride =
    form.modelRoutingKey.trim() !== "" && form.modelRoutingKey.trim() !== emptyDefaultRoutingKey;
  const routingSummary = [
    form.modelRoutingKey.trim() || t("agentsPolicyDefaultRoute"),
    form.modelKey.trim() ? form.modelKey.trim() : "",
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="agent-instance-form-shell">
      <AgentInstanceFormSection
        description={t("agentInstancesFormIdentityDesc")}
        step="1"
        title={t("agentInstancesFormIdentityTitle")}
      >
        <div className="budget-form-grid agent-instance-form">
          <div>
            <FieldLabel required htmlFor="agent-instance-name">
              {t("agentInstancesName")}
            </FieldLabel>
            <input
              id="agent-instance-name"
              disabled={!canWrite}
              value={form.name}
              onChange={(event) => onFieldChange("name", event.target.value)}
            />
          </div>
          <div>
            <FieldLabel required htmlFor="agent-instance-base-agent">
              {t("agentInstancesBaseAgent")}
            </FieldLabel>
            <select
              id="agent-instance-base-agent"
              disabled={!canWrite}
              value={form.agentKey}
              onChange={(event) => onAgentChange(event.target.value)}
            >
              {catalog.map((agent) => (
                <option key={agent.agent_key} value={agent.agent_key}>
                  {agentDisplayName(agent, locale)} · {agent.required_module}
                </option>
              ))}
            </select>
          </div>
          <label>
            {t("agentInstancesVisibility")}
            <select
              disabled={!canWrite}
              value={form.visibility}
              onChange={(event) =>
                onFieldChange("visibility", event.target.value as AgentInstanceFormState["visibility"])
              }
            >
              <option value="tenant">{t("agentInstancesTenantWide")}</option>
              <option value="department">{t("agentInstancesDepartmentScoped")}</option>
              <option value="private">{t("agentInstancesPrivate")}</option>
            </select>
          </label>
        </div>
        <details className="agent-instance-optional-field" open={Boolean(form.slug.trim())}>
          <summary>{t("agentInstancesOptionalIdentity")}</summary>
          <label>
            {t("agentInstancesSlug")}
            <input
              disabled={!canWrite}
              placeholder={t("agentInstancesSlugPlaceholder")}
              value={form.slug}
              onChange={(event) => onFieldChange("slug", event.target.value)}
            />
          </label>
        </details>
      </AgentInstanceFormSection>

      <AgentInstanceFormSection
        collapsible
        defaultOpen={routingHasOverride || Boolean(form.modelKey.trim())}
        description={t("agentInstancesFormRoutingDesc")}
        summary={routingSummary}
        step="2"
        title={t("agentInstancesFormRoutingTitle")}
      >
        <div className="budget-form-grid agent-instance-form">
          <label>
            {t("agentInstancesRoutingKey")}
            <input
              disabled={!canWrite}
              value={form.modelRoutingKey}
              onChange={(event) => onFieldChange("modelRoutingKey", event.target.value)}
            />
          </label>
          <label>
            {t("agentInstancesModelKey")}
            <input
              disabled={!canWrite}
              placeholder={t("agentInstancesModelKeyPlaceholder")}
              value={form.modelKey}
              onChange={(event) => onFieldChange("modelKey", event.target.value)}
            />
          </label>
        </div>
      </AgentInstanceFormSection>

      <AgentInstanceFormSection
        description={t("agentInstancesFormKnowledgeDesc")}
        step="3"
        title={t("agentInstancesFormKnowledgeTitle")}
      >
        <div className="budget-form-grid agent-instance-form">
          <div className="agent-instance-description">
            <AgentKnowledgeBindingPicker
              disabled={!canWrite}
              help={t("agentInstancesDefaultKnowledgeHelp")}
              knowledgeBases={knowledgeBases}
              label={t("agentInstancesDefaultKnowledge")}
              onChange={(ids) => onFieldChange("knowledgeBaseIds", ids)}
              value={form.knowledgeBaseIds}
            />
          </div>
          <label className="agent-instance-description">
            {t("agentInstancesDescription")}
            <textarea
              disabled={!canWrite}
              value={form.description}
              onChange={(event) => onFieldChange("description", event.target.value)}
            />
          </label>
        </div>
      </AgentInstanceFormSection>
    </div>
  );
}

function AgentInstanceFormSection({
  children,
  collapsible = false,
  defaultOpen = true,
  description,
  step,
  summary,
  title,
}: {
  children: ReactNode;
  collapsible?: boolean;
  defaultOpen?: boolean;
  description: string;
  step: string;
  summary?: string;
  title: string;
}) {
  const head = (
    <div className="agent-instance-form-section-head">
      <span>{step}</span>
      <div>
        <strong>{title}</strong>
        <small>{description}</small>
      </div>
    </div>
  );
  if (collapsible) {
    return (
      <details className="agent-instance-form-section collapsible" open={defaultOpen}>
        <summary>
          {head}
          {summary ? <span className="agent-instance-form-section-summary">{summary}</span> : null}
        </summary>
        <div className="agent-instance-form-section-body">{children}</div>
      </details>
    );
  }
  return (
    <section className="agent-instance-form-section">
      {head}
      <div className="agent-instance-form-section-body">{children}</div>
    </section>
  );
}

const emptyDefaultRoutingKey = "default-chat";
