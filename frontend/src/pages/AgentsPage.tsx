import { Boxes, Plus, Route } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiNotice, Button, LoadingState, PageHeader } from "../components/app-ui";
import type { PageId, WorkspaceId } from "../data";
import { useAgentCatalog, useAgentGovernanceTargets, useBudgetPolicies, useChannels } from "../hooks/useAdminData";
import { useLocale } from "../i18n-context";
import type { AgentInstanceResponse, AuthUser } from "../lib/api";
import { showDeliveryDiagnostics } from "../lib/deliveryDiagnostics";
import { canAccess } from "../lib/permissions";
import { AgentInstancesPanel } from "./agents/AgentInstancesPanel";
import { AgentRunDrawer } from "./agents/AgentRunDrawer";

type AgentTabRequest = "instances" | "runtime" | "catalog";
interface AgentTabRequestState {
  requested: boolean;
  tab: AgentTabRequest;
}

const AGENT_TAB_REQUEST_KEY = "agenthive.agents.default_tab";
const AGENT_KEY_REQUEST_KEY = "agenthive.agents.default_agent_key";
const AGENT_KNOWLEDGE_REQUEST_KEY = "agenthive.agents.default_knowledge_base_id";
const CHAT_PRESELECT_AGENT_KEY = "agenthive.chat.preselect_agent_id";
const BUILDER_PRESELECT_INSTANCE_KEY = "agenthive.builder.preselect_instance_id";

function consumeRequestedAgentTab(): AgentTabRequestState {
  const requested = window.sessionStorage.getItem(AGENT_TAB_REQUEST_KEY);
  if (requested === "catalog" || requested === "instances" || requested === "runtime") {
    window.sessionStorage.removeItem(AGENT_TAB_REQUEST_KEY);
    return { requested: true, tab: requested };
  }
  return { requested: false, tab: "instances" };
}

function consumeRequestedAgentKey() {
  const requested = window.sessionStorage.getItem(AGENT_KEY_REQUEST_KEY);
  if (requested) {
    window.sessionStorage.removeItem(AGENT_KEY_REQUEST_KEY);
  }
  return requested;
}

function hasRequestedKnowledgeBase() {
  return Boolean(window.sessionStorage.getItem(AGENT_KNOWLEDGE_REQUEST_KEY));
}

export function AgentsPage({
  activeWorkspace = "admin",
  isPrototype = false,
  onNavigate,
  user = null,
}: {
  activeWorkspace?: WorkspaceId;
  isPrototype?: boolean;
  onNavigate?: (page: PageId) => void;
  user?: AuthUser | null;
}) {
  const { t } = useLocale();
  const showDiagnostics = showDeliveryDiagnostics(activeWorkspace);
  const canWriteAgents = isPrototype || canAccess(user, ["agents:write"]);
  const requestedTabState = useMemo(consumeRequestedAgentTab, []);
  const requestedTab = requestedTabState.tab;
  const requestedAgentKey = useMemo(consumeRequestedAgentKey, []);
  const requestedKnowledgeBase = useMemo(hasRequestedKnowledgeBase, []);
  const [instanceWorkspaceRequest, setInstanceWorkspaceRequest] = useState<"create" | "published" | "readiness" | null>(
    requestedTab === "instances" ? (requestedAgentKey || requestedKnowledgeBase ? "create" : "published") : null,
  );
  const [runtimeAgentKey, setRuntimeAgentKey] = useState<string | null>(
    requestedTab === "runtime" ? requestedAgentKey : null,
  );
  const [runtimeInstanceId, setRuntimeInstanceId] = useState("");
  const { data: catalog, error, loading, refetch } = useAgentCatalog({ fallbackOnError: isPrototype });
  const { data: governanceTargets } = useAgentGovernanceTargets({ fallbackOnError: isPrototype });
  const { data: budgetPolicies } = useBudgetPolicies({ fallbackOnError: isPrototype });
  const { data: channels } = useChannels({ fallbackOnError: isPrototype });
  const agents = catalog ?? [];
  const knowledgeBases = useMemo(
    () =>
      (governanceTargets?.knowledge_bases ?? []).map((target) => ({
        id: target.id,
        name: String(target.metadata.name ?? target.label),
        rag_engine: String(target.metadata.rag_engine ?? ""),
      })),
    [governanceTargets],
  );
  const modelDeployments = useMemo(
    () =>
      (governanceTargets?.model_deployments ?? []).map((target) => ({
        id: target.id,
        label: target.label,
        routing_key: String(target.metadata.routing_key ?? ""),
      })),
    [governanceTargets],
  );
  const [selectedAgentKey, setSelectedAgentKey] = useState<string | null>(requestedAgentKey);
  const [localNotice, setLocalNotice] = useState(() =>
    requestedTabState.requested && requestedTab === "instances"
      ? requestedAgentKey
        ? t("agentsModuleConfigurationFocused")
        : t("agentsKnowledgeBindingFocused")
      : "",
  );
  const selectedAgent = agents.find((agent) => agent.agent_key === selectedAgentKey) ?? agents[0] ?? null;
  const runtimeAgent =
    agents.find((agent) => agent.agent_key === runtimeAgentKey) ?? (runtimeAgentKey ? selectedAgent : null);

  useEffect(() => {
    if (requestedTab === "catalog") {
      onNavigate?.("agentModules");
    }
  }, [onNavigate, requestedTab]);

  useEffect(() => {
    if (!agents.length) {
      return;
    }
    if (!selectedAgentKey || !agents.some((agent) => agent.agent_key === selectedAgentKey)) {
      setSelectedAgentKey(agents[0]?.agent_key ?? null);
    }
  }, [agents, selectedAgentKey]);

  const focusCreateForm = () => {
    if (!canWriteAgents) {
      setLocalNotice(t("agentsWritePermissionRequiredDetail"));
      window.setTimeout(() => setLocalNotice(""), 2600);
      return;
    }
    setInstanceWorkspaceRequest("create");
    setLocalNotice(t("agentsCreateFocused"));
    window.setTimeout(() => setLocalNotice(""), 2600);
    document.getElementById("agent-instance-panel")?.scrollIntoView({ behavior: "smooth", block: "start" });
    window.setTimeout(() => {
      document.querySelector<HTMLInputElement>("#agent-instance-panel input")?.focus();
    }, 250);
  };
  const openModuleCatalog = () => {
    onNavigate?.("agentModules");
  };
  const openBudgets = () => {
    onNavigate?.("budgets");
  };
  const openChannels = () => {
    onNavigate?.("channels");
  };
  const consumeInstanceWorkspaceRequest = useCallback(() => setInstanceWorkspaceRequest(null), []);

  const openRuntimeDrawer = () => {
    if (selectedAgent) {
      setRuntimeAgentKey(selectedAgent.agent_key);
      setRuntimeInstanceId("");
    }
  };
  const openInstanceRuntimeDrawer = (instance: AgentInstanceResponse) => {
    setSelectedAgentKey(instance.agent_key);
    setRuntimeAgentKey(instance.agent_key);
    setRuntimeInstanceId(instance.id);
  };
  const openChatWithInstance = (instance: AgentInstanceResponse) => {
    window.sessionStorage.setItem(CHAT_PRESELECT_AGENT_KEY, instance.id);
    onNavigate?.("chatConsole");
  };
  const openBuilderWithInstance = (instance: AgentInstanceResponse) => {
    window.sessionStorage.setItem(BUILDER_PRESELECT_INSTANCE_KEY, instance.id);
    onNavigate?.("builder");
  };

  return (
    <section className="page">
      <PageHeader
        title={t("agentsTitle")}
        subtitle={t("agentsSubtitleSlim")}
        actions={
          <>
            <Button onClick={openRuntimeDrawer} disabled={!selectedAgent}>
              <Route size={16} /> {t("agentsTabRuntime")}
            </Button>
            <Button onClick={openModuleCatalog}>
              <Boxes size={16} /> {t("agentsOpenModuleCatalog")}
            </Button>
            <Button variant="primary" onClick={focusCreateForm} disabled={!canWriteAgents}>
              <Plus size={16} /> {t("agentsCreate")}
            </Button>
          </>
        }
      />
      {loading && !agents.length && <LoadingState message={t("agentsLoadingMessage")} lines={3} />}
      {loading && !!agents.length && (
        <div className="refresh-indicator" role="status" aria-live="polite">
          <span className="refresh-spinner" aria-hidden="true" />
          {t("commonRefreshing")}
        </div>
      )}
      {error && !loading && (
        <ApiNotice
          title={t("agentsLoadErrorTitle")}
          message={error}
          action={<Button onClick={refetch}>{t("commonRetry")}</Button>}
        />
      )}
      {localNotice && <div className="form-message">{localNotice}</div>}
      <AgentInstancesPanel
        canWrite={canWriteAgents}
        catalog={agents}
        budgetPolicies={budgetPolicies ?? []}
        isPrototype={isPrototype}
        channels={channels ?? []}
        knowledgeBases={knowledgeBases}
        modelDeployments={modelDeployments}
        onOpenBudgets={openBudgets}
        onOpenChannels={openChannels}
        onOpenCatalog={openModuleCatalog}
        onRunInstance={openInstanceRuntimeDrawer}
        onWorkspaceTabRequestConsumed={consumeInstanceWorkspaceRequest}
        requestedWorkspaceTab={instanceWorkspaceRequest}
        selectedAgentKey={selectedAgent?.agent_key ?? null}
        showDiagnostics={showDiagnostics}
        onChatInstance={openChatWithInstance}
        onConfigureInstance={openBuilderWithInstance}
      />
      {runtimeAgent && (
        <AgentRunDrawer
          agent={runtimeAgent}
          initialInstanceId={runtimeInstanceId}
          isPrototype={isPrototype}
          key={`${runtimeAgent.agent_key}:${runtimeInstanceId || "policy-default"}`}
          knowledgeBases={knowledgeBases}
          onClose={() => {
            setRuntimeAgentKey(null);
            setRuntimeInstanceId("");
          }}
        />
      )}
    </section>
  );
}
