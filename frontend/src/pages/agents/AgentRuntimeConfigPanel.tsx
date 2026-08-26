import { Plus } from "lucide-react";
import { ApiNotice, PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import { agentDisplayName } from "../../lib/agentDisplay";
import type { AgentCatalogEntryResponse, AgentInstanceResponse } from "../../lib/api";
import {
  type AgentKnowledgeBaseOption,
  knowledgeBaseBindingsForInstance,
  knowledgeBaseIdsFromConfig,
} from "./agentInstanceUtils";
import type { AgentRuntimeConfigTab } from "./agentRuntimeTypes";
import { formatLicenseGateDetail } from "./agentUtils";
import { RuntimeRouteSummary } from "./RuntimeRouteSummary";

interface AgentRuntimeConfigPanelProps {
  activeConfigTab: AgentRuntimeConfigTab;
  agent: AgentCatalogEntryResponse;
  availableInstances: AgentInstanceResponse[];
  instanceId: string;
  knowledgeBaseId: string;
  knowledgeBases: AgentKnowledgeBaseOption[];
  mediaAgent: boolean;
  onConfigTabChange: (tab: AgentRuntimeConfigTab) => void;
  onInstanceIdChange: (instanceId: string) => void;
  onKnowledgeBaseIdChange: (knowledgeBaseId: string) => void;
  selectedInstance: AgentInstanceResponse | null;
}

export function AgentRuntimeConfigPanel({
  activeConfigTab,
  agent,
  availableInstances,
  instanceId,
  knowledgeBaseId,
  knowledgeBases,
  mediaAgent,
  onConfigTabChange,
  onInstanceIdChange,
  onKnowledgeBaseIdChange,
  selectedInstance,
}: AgentRuntimeConfigPanelProps) {
  const { t } = useLocale();

  return (
    <div className="nested-workspace agent-runtime-config-workspace">
      <PageTabs
        active={activeConfigTab}
        onChange={onConfigTabChange}
        tabs={[
          {
            id: "route",
            label: t("agentsRuntimeConfigRouteTab"),
            description: t("agentsRuntimeConfigRouteTabDesc"),
          },
          {
            id: "knowledge",
            label: t("agentsRuntimeConfigKnowledgeTab"),
            description: t("agentsRuntimeConfigKnowledgeTabDesc"),
          },
          {
            id: "module",
            label: t("agentsRuntimeConfigModuleTab"),
            description: t("agentsRuntimeConfigModuleTabDesc"),
          },
        ]}
      />
      {activeConfigTab === "route" && (
        <RuntimeRoutePanel
          availableInstances={availableInstances}
          instanceId={instanceId}
          onInstanceIdChange={onInstanceIdChange}
          selectedInstance={selectedInstance}
        />
      )}
      {activeConfigTab === "knowledge" && (
        <RuntimeKnowledgePanel
          knowledgeBaseId={knowledgeBaseId}
          knowledgeBases={knowledgeBases}
          mediaAgent={mediaAgent}
          onKnowledgeBaseIdChange={onKnowledgeBaseIdChange}
          selectedInstance={selectedInstance}
        />
      )}
      {activeConfigTab === "module" && <RuntimeModulePanel agent={agent} />}
    </div>
  );
}

function RuntimeRoutePanel({
  availableInstances,
  instanceId,
  onInstanceIdChange,
  selectedInstance,
}: {
  availableInstances: AgentInstanceResponse[];
  instanceId: string;
  onInstanceIdChange: (instanceId: string) => void;
  selectedInstance: AgentInstanceResponse | null;
}) {
  const { locale, t } = useLocale();

  return (
    <>
      <h3>{t("agentsRuntimeRoute")}</h3>
      <label>
        {t("agentsRuntimeInstance")}
        <select value={instanceId} onChange={(event) => onInstanceIdChange(event.target.value)}>
          <option value="">{t("agentsPolicyDefaultRoute")}</option>
          {availableInstances.map((instance) => (
            <option key={instance.id} value={instance.id}>
              {agentDisplayName(instance, locale)} · {instance.model_routing_key ?? t("agentsPolicyDefault")}
            </option>
          ))}
        </select>
      </label>
      <RuntimeRouteSummary instance={selectedInstance} />
    </>
  );
}

function RuntimeKnowledgePanel({
  knowledgeBaseId,
  knowledgeBases,
  mediaAgent,
  onKnowledgeBaseIdChange,
  selectedInstance,
}: {
  knowledgeBaseId: string;
  knowledgeBases: AgentKnowledgeBaseOption[];
  mediaAgent: boolean;
  onKnowledgeBaseIdChange: (knowledgeBaseId: string) => void;
  selectedInstance: AgentInstanceResponse | null;
}) {
  const { t } = useLocale();
  const instanceKnowledgeBaseIds = knowledgeBaseIdsFromConfig(selectedInstance?.config);
  const instanceKnowledgeBindings = selectedInstance
    ? knowledgeBaseBindingsForInstance(selectedInstance, knowledgeBases)
    : [];

  return (
    <>
      <h3>{t("agentsKnowledgeBase")}</h3>
      {mediaAgent ? (
        <ApiNotice title={t("agentsKnowledgeNotEnabled")} message={t("agentsMediaKnowledgeNotNeeded")} />
      ) : (
        <>
          {selectedInstance && (
            <div className="agent-instance-knowledge-summary">
              <span>{t("agentInstancesDefaultKnowledge")}</span>
              {instanceKnowledgeBindings.length ? (
                <div>
                  {instanceKnowledgeBindings.map((binding) => (
                    <small key={binding.id}>{binding.label}</small>
                  ))}
                </div>
              ) : (
                <p>{t("agentsNoKnowledgeBase")}</p>
              )}
            </div>
          )}
          <label>
            {t("agentsKnowledgeBase")}
            <select value={knowledgeBaseId} onChange={(event) => onKnowledgeBaseIdChange(event.target.value)}>
              <option value="">
                {instanceKnowledgeBaseIds.length
                  ? t("agentsUseInstanceKnowledge").replace("{{count}}", String(instanceKnowledgeBaseIds.length))
                  : t("agentsNoKnowledgeBase")}
              </option>
              {knowledgeBases.map((base) => (
                <option key={base.id} value={base.id}>
                  {base.name} · {base.rag_engine}
                </option>
              ))}
            </select>
          </label>
        </>
      )}
    </>
  );
}

function RuntimeModulePanel({ agent }: { agent: AgentCatalogEntryResponse }) {
  const { t } = useLocale();

  return (
    <>
      <h3>{t("agentsCoreConfig")}</h3>
      <label>
        {t("agentsRequiredModule")}
        <select>
          <option>{agent.required_module}</option>
        </select>
      </label>
      <div className="field-block">
        <span>{t("agentsLicenseGate")}</span>
        <p>{formatLicenseGateDetail(agent, t)}</p>
      </div>
      <div className="prompt-box">
        <div>
          <h3>{t("agentsDescription")}</h3>
        </div>
        <pre>{agent.description}</pre>
      </div>
      <h3>
        {t("agentsCapabilities")} <Plus size={17} />
      </h3>
      {agent.capabilities.map((capability) => (
        <div className="kb-chip" key={capability}>
          {capability}
        </div>
      ))}
    </>
  );
}
