import { CheckCircle2, PauseCircle, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Button, cx, Drawer, FormField, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import { agentDisplayName } from "../../lib/agentDisplay";
import type { AgentInstanceResponse, AgentInstanceUpdateRequest } from "../../lib/api";
import { readinessReasonLabel } from "../../lib/readiness";
import { AgentAssignmentPanel } from "./AgentAssignmentPanel";
import { AgentKnowledgeBindingPicker } from "./AgentKnowledgeBindingPicker";
import {
  type AgentInstanceFormState,
  type AgentKnowledgeBaseOption,
  knowledgeBaseIdsFromConfig,
} from "./agentInstanceUtils";

interface AgentInstanceDrawerProps {
  canWrite: boolean;
  instance: AgentInstanceResponse;
  knowledgeBases: AgentKnowledgeBaseOption[];
  onClose: () => void;
  onSave: (instance: AgentInstanceResponse, payload: AgentInstanceUpdateRequest) => Promise<void>;
  onSetStatus: (instance: AgentInstanceResponse, status: "active" | "disabled") => Promise<void>;
  saving: boolean;
}

export function AgentInstanceDrawer({
  canWrite,
  instance,
  knowledgeBases,
  onClose,
  onSave,
  onSetStatus,
  saving,
}: AgentInstanceDrawerProps) {
  const { locale, t } = useLocale();
  const [form, setForm] = useState(() => formFromInstance(instance));
  const [nameError, setNameError] = useState<string | null>(null);
  const knowledgeLabels = useMemo(
    () => knowledgeLabelsForIds(form.knowledgeBaseIds, knowledgeBases),
    [form.knowledgeBaseIds, knowledgeBases],
  );

  useEffect(() => {
    setForm(formFromInstance(instance));
    setNameError(null);
  }, [instance]);

  const updateField = <K extends keyof AgentInstanceFormState>(field: K, value: AgentInstanceFormState[K]) => {
    setForm((current) => ({ ...current, [field]: value }));
    if (field === "name") {
      setNameError(null);
    }
  };

  const validateForm = (): boolean => {
    const name = form.name.trim();
    if (!name) {
      setNameError(t("agentInstancesNameRequired"));
      return false;
    }
    if (name.length < 2) {
      setNameError(t("agentInstancesNameTooShort"));
      return false;
    }
    setNameError(null);
    return true;
  };

  const save = async () => {
    if (!validateForm()) {
      return;
    }
    await onSave(instance, {
      config: {
        ...instance.config,
        knowledge_base_ids: form.knowledgeBaseIds,
        knowledge_top_k: instance.config.knowledge_top_k ?? 3,
      },
      description: form.description.trim() || null,
      model_key: form.modelKey.trim() || null,
      model_routing_key: form.modelRoutingKey.trim() || null,
      name: form.name.trim(),
      visibility: form.visibility,
    });
  };

  return (
    <Drawer
      open={true}
      title={agentDisplayName(instance, locale)}
      subtitle={`${instance.agent_key} · ${instance.module_key}`}
      onClose={onClose}
      ariaLabel={t("agentInstancesDetail")}
      className="agent-instance-drawer"
      footer={
        <>
          <div className="drawer-footer-actions">
            <Button
              disabled={!canWrite || saving || instance.status === "active"}
              onClick={() => void onSetStatus(instance, "active")}
            >
              <CheckCircle2 size={16} /> {t("agentInstancesEnable")}
            </Button>
            <Button
              disabled={!canWrite || saving || instance.status === "disabled"}
              onClick={() => void onSetStatus(instance, "disabled")}
            >
              <PauseCircle size={16} /> {t("agentInstancesDisable")}
            </Button>
          </div>
          <Button variant="primary" disabled={!canWrite || saving} onClick={() => void save()}>
            <Save size={16} /> {saving ? t("commonSaving") : t("agentInstancesSave")}
          </Button>
        </>
      }
    >
      <div className="agent-instance-drawer-content">
        <section className="agent-instance-detail-section">
          <div className="agent-instance-detail-title">
            <strong>{t("agentInstancesDetailOverview")}</strong>
            <StatusBadge status={instance.status} />
          </div>
          <div className="agent-instance-detail-grid">
            <DetailItem label={t("agentInstancesVisibility")} value={instance.visibility} />
            <DetailItem label={t("agentInstancesSlug")} value={instance.slug} />
            <DetailItem
              label={t("agentInstancesRoute")}
              value={instance.model_routing_key ?? t("agentsPolicyDefault")}
            />
            <DetailItem
              label={t("agentInstancesKnowledge")}
              value={knowledgeLabels.length ? String(knowledgeLabels.length) : t("agentsNoKnowledgeBase")}
            />
            <DetailItem
              label={t("agentInstancesUpdatedAt")}
              value={new Date(instance.updated_at).toLocaleString(locale)}
            />
          </div>
        </section>

        <section className="agent-instance-detail-section">
          <div className="agent-instance-detail-title">
            <strong>{t("agentInstancesDetailConfig")}</strong>
            <span>{t("agentInstancesDetailConfigHint")}</span>
          </div>
          <div className="budget-form-grid agent-instance-form">
            <FormField htmlFor="agent-instance-name" label={t("agentInstancesName")} error={nameError}>
              <input
                id="agent-instance-name"
                disabled={!canWrite}
                value={form.name}
                onChange={(event) => updateField("name", event.target.value)}
                className={cx(nameError ? "form-input-error" : undefined)}
                aria-invalid={nameError ? true : undefined}
              />
            </FormField>
            <label>
              {t("agentInstancesVisibility")}
              <select
                disabled={!canWrite}
                value={form.visibility}
                onChange={(event) =>
                  updateField("visibility", event.target.value as AgentInstanceFormState["visibility"])
                }
              >
                <option value="tenant">{t("agentInstancesTenantWide")}</option>
                <option value="department">{t("agentInstancesDepartmentScoped")}</option>
                <option value="private">{t("agentInstancesPrivate")}</option>
              </select>
            </label>
            <label>
              {t("agentInstancesRoutingKey")}
              <input
                disabled={!canWrite}
                value={form.modelRoutingKey}
                onChange={(event) => updateField("modelRoutingKey", event.target.value)}
              />
            </label>
            <label>
              {t("agentInstancesModelKey")}
              <input
                disabled={!canWrite}
                placeholder={t("agentInstancesModelKeyPlaceholder")}
                value={form.modelKey}
                onChange={(event) => updateField("modelKey", event.target.value)}
              />
            </label>
            <label className="agent-instance-description">
              {t("agentInstancesDescription")}
              <textarea
                disabled={!canWrite}
                value={form.description}
                onChange={(event) => updateField("description", event.target.value)}
              />
            </label>
          </div>
        </section>

        <section className="agent-instance-detail-section">
          <div className="agent-instance-detail-title">
            <strong>{t("agentInstancesDetailKnowledge")}</strong>
            <span>{t("agentInstancesDefaultKnowledgeHelp")}</span>
          </div>
          <AgentKnowledgeBindingPicker
            disabled={!canWrite}
            knowledgeBases={knowledgeBases}
            label={t("agentInstancesDefaultKnowledge")}
            onChange={(ids) => updateField("knowledgeBaseIds", ids)}
            value={form.knowledgeBaseIds}
          />
          <div className="agent-instance-knowledge-summary">
            {knowledgeLabels.length ? (
              knowledgeLabels.map((label) => <span key={label}>{label}</span>)
            ) : (
              <p>{t("agentsNoKnowledgeBase")}</p>
            )}
          </div>
        </section>

        <AgentAssignmentPanel agentId={instance.id} canWrite={canWrite} />

        <section className={cx("agent-instance-detail-section", instance.runnable === false && "warning")}>
          <div className="agent-instance-detail-title">
            <strong>{t("agentInstancesDetailReadiness")}</strong>
            <span>
              {instance.runnable !== false
                ? t("agentInstancesReadyForHandoff")
                : t("agentInstancesReadinessNeedsReview")}
            </span>
          </div>
          {instance.runnable === false ? (
            <div className="agent-instance-readiness-reasons">
              {(instance.readiness_reasons ?? []).map((reason) => (
                <span key={reason}>{readinessReasonLabel(reason, t)}</span>
              ))}
            </div>
          ) : (
            <p className="agent-instance-ready-note">{t("agentInstancesReadinessReadyMessage")}</p>
          )}
        </section>
      </div>
    </Drawer>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formFromInstance(instance: AgentInstanceResponse): AgentInstanceFormState {
  return {
    agentKey: instance.agent_key,
    description: instance.description ?? "",
    knowledgeBaseIds: knowledgeBaseIdsFromConfig(instance.config),
    modelKey: instance.model_key ?? "",
    modelRoutingKey: instance.model_routing_key ?? "",
    name: instance.name,
    slug: instance.slug,
    visibility: instance.visibility,
  };
}

function knowledgeLabelsForIds(ids: string[], knowledgeBases: AgentKnowledgeBaseOption[]) {
  const labels = new Map(knowledgeBases.map((base) => [base.id, `${base.name} · ${base.rag_engine}`]));
  return ids.map((id) => labels.get(id) ?? id);
}
