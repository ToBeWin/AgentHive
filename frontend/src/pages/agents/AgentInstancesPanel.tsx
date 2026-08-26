import { Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { ApiNotice, Button, cx, PageTabs } from "../../components/app-ui";
import { useAgentInstanceActions, useAgentInstances } from "../../hooks/useAdminData";
import { useLocale } from "../../i18n-context";
import type {
  AgentCatalogEntryResponse,
  AgentInstanceCreateRequest,
  AgentInstanceResponse,
  AgentInstanceUpdateRequest,
  BudgetPolicyResponse,
  ChannelResponse,
} from "../../lib/api";
import { AgentInstanceDrawer } from "./AgentInstanceDrawer";
import { AgentInstanceForm } from "./AgentInstanceForm";
import { AgentInstanceReadinessPanel } from "./AgentInstanceReadinessPanel";
import { AgentInstanceTable } from "./AgentInstanceTable";
import { AgentRolloutLoopPanel } from "./AgentRolloutLoopPanel";
import {
  type AgentInstanceFormState,
  type AgentKnowledgeBaseOption,
  type AgentModelDeploymentOption,
  defaultInstanceDescription,
  defaultInstanceName,
  emptyAgentInstanceForm,
} from "./agentInstanceUtils";
import { formatLicenseGate } from "./agentUtils";

interface AgentInstancesPanelProps {
  budgetPolicies: BudgetPolicyResponse[];
  canWrite: boolean;
  catalog: AgentCatalogEntryResponse[];
  channels: ChannelResponse[];
  isPrototype?: boolean;
  knowledgeBases: AgentKnowledgeBaseOption[];
  modelDeployments: AgentModelDeploymentOption[];
  onOpenBudgets: () => void;
  onOpenChannels: () => void;
  onOpenCatalog: () => void;
  onRunInstance: (instance: AgentInstanceResponse) => void;
  onWorkspaceTabRequestConsumed?: () => void;
  requestedWorkspaceTab?: AgentInstanceWorkspaceTab | null;
  selectedAgentKey: string | null;
  showDiagnostics?: boolean;
  onChatInstance?: (instance: AgentInstanceResponse) => void;
  onConfigureInstance?: (instance: AgentInstanceResponse) => void;
}

type AgentInstanceWorkspaceTab = "create" | "published" | "readiness";

const AGENT_KNOWLEDGE_REQUEST_KEY = "agenthive.agents.default_knowledge_base_id";

function consumeRequestedKnowledgeBaseId() {
  const requested = window.sessionStorage.getItem(AGENT_KNOWLEDGE_REQUEST_KEY);
  if (requested) {
    window.sessionStorage.removeItem(AGENT_KNOWLEDGE_REQUEST_KEY);
  }
  return requested ?? "";
}

export function AgentInstancesPanel({
  budgetPolicies,
  canWrite,
  catalog,
  channels,
  isPrototype = false,
  knowledgeBases,
  modelDeployments,
  onOpenBudgets,
  onOpenChannels,
  onOpenCatalog,
  onRunInstance,
  onWorkspaceTabRequestConsumed,
  requestedWorkspaceTab,
  selectedAgentKey,
  showDiagnostics = false,
  onChatInstance,
  onConfigureInstance,
}: AgentInstancesPanelProps) {
  const { locale, t } = useLocale();
  const { data: instances, error, loading, refetch } = useAgentInstances({ fallbackOnError: isPrototype });
  const actions = useAgentInstanceActions({ fallbackOnError: isPrototype });
  const [workspaceTab, setWorkspaceTab] = useState<AgentInstanceWorkspaceTab>("published");
  const [selectedInstanceId, setSelectedInstanceId] = useState<string | null>(null);
  const [form, setForm] = useState<AgentInstanceFormState>(() => {
    const requestedKnowledgeBaseId = consumeRequestedKnowledgeBaseId();
    return {
      ...emptyAgentInstanceForm,
      knowledgeBaseIds: requestedKnowledgeBaseId ? [requestedKnowledgeBaseId] : [],
    };
  });

  const selectedCatalogAgent = useMemo(
    () => catalog.find((agent) => agent.agent_key === form.agentKey) ?? null,
    [catalog, form.agentKey],
  );
  const instanceList = instances ?? [];
  const selectedInstance = instanceList.find((instance) => instance.id === selectedInstanceId) ?? null;

  useEffect(() => {
    if (!requestedWorkspaceTab) {
      return;
    }
    if (!showDiagnostics && requestedWorkspaceTab === "readiness") {
      setWorkspaceTab("published");
      onWorkspaceTabRequestConsumed?.();
      return;
    }
    setWorkspaceTab(requestedWorkspaceTab);
    onWorkspaceTabRequestConsumed?.();
  }, [onWorkspaceTabRequestConsumed, requestedWorkspaceTab, showDiagnostics]);

  useEffect(() => {
    if (!showDiagnostics && workspaceTab === "readiness") {
      setWorkspaceTab("published");
    }
  }, [showDiagnostics, workspaceTab]);

  useEffect(() => {
    const nextAgentKey = selectedAgentKey ?? catalog[0]?.agent_key ?? "";
    if (!form.agentKey && nextAgentKey) {
      setForm((current) => ({
        ...current,
        agentKey: nextAgentKey,
        description: current.description || defaultInstanceDescription(catalog, nextAgentKey, locale),
        name: current.name || defaultInstanceName(catalog, nextAgentKey, locale),
      }));
    }
  }, [catalog, form.agentKey, locale, selectedAgentKey]);

  const updateField = <K extends keyof AgentInstanceFormState>(field: K, value: AgentInstanceFormState[K]) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const changeAgent = (agentKey: string) => {
    setForm((current) => ({
      ...current,
      agentKey,
      description: current.description || defaultInstanceDescription(catalog, agentKey, locale),
      name: current.name || defaultInstanceName(catalog, agentKey, locale),
    }));
  };

  const createInstance = async () => {
    if (!canWrite || !form.name.trim() || !form.agentKey) {
      return;
    }
    const payload: AgentInstanceCreateRequest = {
      agent_key: form.agentKey,
      config: {
        knowledge_base_ids: form.knowledgeBaseIds,
        knowledge_top_k: 3,
      },
      description: form.description.trim() || null,
      metadata: { source: "agents_page" },
      model_key: form.modelKey.trim() || null,
      model_routing_key: form.modelRoutingKey.trim() || null,
      name: form.name.trim(),
      slug: form.slug.trim() || null,
      visibility: form.visibility,
    };
    const created = await actions.createAgentInstance(payload);
    if (created) {
      setForm((current) => ({
        ...emptyAgentInstanceForm,
        agentKey: current.agentKey,
        modelRoutingKey: current.modelRoutingKey,
      }));
      setWorkspaceTab("published");
      await refetch();
    }
  };

  const setInstanceStatus = async (instance: AgentInstanceResponse, status: "active" | "disabled") => {
    if (!canWrite) {
      return;
    }
    const updated = await actions.updateAgentInstance(instance.id, { status });
    if (updated) {
      await refetch();
    }
  };

  const saveInstance = async (instance: AgentInstanceResponse, payload: AgentInstanceUpdateRequest) => {
    if (!canWrite) {
      return;
    }
    const updated = await actions.updateAgentInstance(instance.id, payload);
    if (updated) {
      setSelectedInstanceId(updated.id);
      await refetch();
    }
  };

  return (
    <section className="panel agent-instance-panel" id="agent-instance-panel">
      <div className="panel-title">
        <div>
          <h2>{t("agentInstancesTitle")}</h2>
          <p>{t("agentInstancesSubtitle")}</p>
        </div>
        <Button onClick={refetch} disabled={loading}>
          {t("agentInstancesRefresh")}
        </Button>
      </div>
      {error && <ApiNotice title={t("agentInstancesLoadError")} message={error} />}
      {!canWrite && (
        <ApiNotice title={t("agentsWritePermissionRequired")} message={t("agentsWritePermissionRequiredDetail")} />
      )}
      {(actions.error || actions.message) && (
        <div className={cx("form-message", actions.error ? "error" : false)}>{actions.error ?? actions.message}</div>
      )}
      {showDiagnostics ? (
        <AgentRolloutLoopPanel
          catalog={catalog}
          budgetPolicies={budgetPolicies}
          channels={channels}
          instances={instanceList}
          knowledgeBases={knowledgeBases}
          modelDeployments={modelDeployments}
          onOpenBudgets={onOpenBudgets}
          onOpenChannels={onOpenChannels}
          onOpenCatalog={onOpenCatalog}
          onRunInstance={onRunInstance}
          onSelectWorkspaceTab={setWorkspaceTab}
          workspaceTab={workspaceTab}
        />
      ) : null}
      <PageTabs
        active={workspaceTab}
        onChange={setWorkspaceTab}
        tabs={[
          {
            id: "create",
            label: t("agentInstancesWorkspaceCreate"),
            description: t("agentInstancesWorkspaceCreateDesc"),
          },
          {
            id: "published",
            label: t("agentInstancesWorkspacePublished").replace("{{count}}", String(instanceList.length)),
            description: t("agentInstancesWorkspacePublishedDesc"),
          },
          ...(showDiagnostics
            ? [
                {
                  id: "readiness" as const,
                  label: t("agentInstancesWorkspaceReadiness"),
                  description: t("agentInstancesWorkspaceReadinessDesc"),
                },
              ]
            : []),
        ]}
      />
      {workspaceTab === "create" && (
        <div className="agent-instance-workspace">
          <AgentInstanceForm
            canWrite={canWrite}
            catalog={catalog}
            form={form}
            knowledgeBases={knowledgeBases}
            onAgentChange={changeAgent}
            onFieldChange={updateField}
          />
          {selectedCatalogAgent && (
            <div className="inline-note">
              {t("agentInstancesBasedOn")} <strong>{selectedCatalogAgent.name}</strong>, {t("agentInstancesModule")}{" "}
              <code>{selectedCatalogAgent.required_module}</code>. {t("agentsLicenseGate")}:{" "}
              {formatLicenseGate(selectedCatalogAgent, t)}.
            </div>
          )}
          <div className="provider-actions agent-instance-actions">
            <Button
              variant="primary"
              onClick={createInstance}
              disabled={!canWrite || actions.saving || !form.name.trim() || !form.agentKey}
            >
              <Plus size={16} /> {t("agentInstancesCreate")}
            </Button>
          </div>
        </div>
      )}
      {workspaceTab === "published" && (
        <AgentInstanceTable
          canWrite={canWrite}
          instances={instanceList}
          knowledgeBases={knowledgeBases}
          loading={loading}
          onCreate={() => setWorkspaceTab("create")}
          onInspect={(instance) => setSelectedInstanceId(instance.id)}
          onRun={onRunInstance}
          onSetStatus={(instance, status) => void setInstanceStatus(instance, status)}
          onChat={onChatInstance}
          onConfigure={onConfigureInstance}
          saving={actions.saving}
        />
      )}
      {workspaceTab === "readiness" && (
        <AgentInstanceReadinessPanel
          budgetPolicies={budgetPolicies}
          channels={channels}
          instances={instanceList}
          knowledgeBases={knowledgeBases}
          onOpenBudgets={onOpenBudgets}
          onOpenChannels={onOpenChannels}
          onCreateInstance={() => setWorkspaceTab("create")}
          onOpenPublished={() => setWorkspaceTab("published")}
          onRunInstance={onRunInstance}
        />
      )}
      {selectedInstance && (
        <AgentInstanceDrawer
          canWrite={canWrite}
          instance={selectedInstance}
          knowledgeBases={knowledgeBases}
          onClose={() => setSelectedInstanceId(null)}
          onSave={saveInstance}
          onSetStatus={setInstanceStatus}
          saving={actions.saving}
        />
      )}
    </section>
  );
}
