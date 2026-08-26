import { SendHorizontal } from "lucide-react";
import { useState } from "react";
import { Button, Drawer, PageTabs } from "../../components/app-ui";
import { useAgentInstances, useAgentRunner } from "../../hooks/useAdminData";
import { useLocale } from "../../i18n-context";
import { agentDisplayName } from "../../lib/agentDisplay";
import type { AgentCatalogEntryResponse } from "../../lib/api";
import { AgentRuntimeConfigPanel } from "./AgentRuntimeConfigPanel";
import { AgentRuntimeEvidencePanel } from "./AgentRuntimeEvidencePanel";
import { AgentRuntimeTestPanel } from "./AgentRuntimeTestPanel";
import { type AgentKnowledgeBaseOption, knowledgeBaseIdsFromConfig } from "./agentInstanceUtils";
import type { AgentRuntimeConfigTab, AgentRuntimeTab, AgentRuntimeTestTab } from "./agentRuntimeTypes";
import { isMediaAgent, mediaRoutingKey, mediaRunContext } from "./agentUtils";

export function AgentRunDrawer({
  agent,
  initialInstanceId = "",
  isPrototype = false,
  knowledgeBases,
  onClose,
}: {
  agent: AgentCatalogEntryResponse;
  initialInstanceId?: string;
  isPrototype?: boolean;
  knowledgeBases: AgentKnowledgeBaseOption[];
  onClose: () => void;
}) {
  const { locale, t } = useLocale();
  const runner = useAgentRunner({ fallbackOnError: isPrototype });
  const { data: instances } = useAgentInstances({ fallbackOnError: isPrototype });
  const mediaAgent = isMediaAgent(agent);
  const [activeRuntimeTab, setActiveRuntimeTab] = useState<AgentRuntimeTab>("config");
  const [activeConfigTab, setActiveConfigTab] = useState<AgentRuntimeConfigTab>("route");
  const [activeTestTab, setActiveTestTab] = useState<AgentRuntimeTestTab>("input");
  const [input, setInput] = useState(defaultAgentInput(agent.agent_key, t));
  const [inputError, setInputError] = useState<string | null>(null);
  const [knowledgeBaseId, setKnowledgeBaseId] = useState("");
  const [instanceId, setInstanceId] = useState(initialInstanceId);
  const availableInstances = (instances ?? []).filter((instance) => instance.agent_key === agent.agent_key);
  const selectedInstance = availableInstances.find((instance) => instance.id === instanceId) ?? null;
  const instanceKnowledgeBaseIds = knowledgeBaseIdsFromConfig(selectedInstance?.config);
  const effectiveKnowledgeBaseIds = knowledgeBaseId ? [knowledgeBaseId] : instanceKnowledgeBaseIds;

  const handleInputChange = (value: string) => {
    setInput(value);
    if (inputError) setInputError(null);
  };

  const runAgent = async () => {
    if (!input.trim()) {
      setInputError(t("agentsRuntimeInputRequired"));
      return;
    }
    const response = await runner.run(agent.agent_key, {
      input,
      context: {
        ...(mediaAgent ? mediaRunContext(agent.agent_key) : {}),
        ...(!mediaAgent && effectiveKnowledgeBaseIds.length
          ? { knowledge_base_ids: effectiveKnowledgeBaseIds, knowledge_top_k: 3 }
          : {}),
        ...(selectedInstance
          ? {
              agent_id: selectedInstance.id,
              agent_instance_slug: selectedInstance.slug,
              department_id: selectedInstance.department_id,
              visibility: selectedInstance.visibility,
            }
          : {}),
        shop_policy: "支持签收后7天内未穿着商品换码，客户需保持吊牌和包装完整。",
        tone: "耐心、明确、可直接发送",
      },
      max_tokens: 1024,
      model_key: selectedInstance?.model_key ?? null,
      routing_key: selectedInstance?.model_routing_key ?? mediaRoutingKey(agent.agent_key),
    });
    if (response) {
      setActiveTestTab("result");
      setActiveRuntimeTab("evidence");
    }
  };

  return (
    <Drawer
      open={true}
      title={agentDisplayName(agent, locale)}
      subtitle={`${agent.agent_key} · ${agent.status}`}
      onClose={onClose}
      ariaLabel={t("agentsTabRuntime")}
      footer={
        <>
          <Button onClick={onClose}>{t("commonClose")}</Button>
          <Button variant="primary" onClick={runAgent} disabled={runner.running || !input.trim()}>
            <SendHorizontal size={16} /> {runner.running ? t("agentsRunning") : t("agentsRunAgent")}
          </Button>
        </>
      }
    >
      <PageTabs
        active={activeRuntimeTab}
        onChange={setActiveRuntimeTab}
        tabs={[
          { id: "config", label: t("agentsRuntimeTabConfig"), description: t("agentsRuntimeTabConfigDesc") },
          { id: "test", label: t("agentsRuntimeTabTest"), description: t("agentsRuntimeTabTestDesc") },
          {
            id: "evidence",
            label: t("agentsRuntimeTabEvidence"),
            description: t("agentsRuntimeTabEvidenceDesc"),
          },
        ]}
      />
      {activeRuntimeTab === "config" && (
        <AgentRuntimeConfigPanel
          activeConfigTab={activeConfigTab}
          agent={agent}
          availableInstances={availableInstances}
          instanceId={instanceId}
          knowledgeBaseId={knowledgeBaseId}
          knowledgeBases={knowledgeBases}
          mediaAgent={mediaAgent}
          onConfigTabChange={setActiveConfigTab}
          onInstanceIdChange={setInstanceId}
          onKnowledgeBaseIdChange={setKnowledgeBaseId}
          selectedInstance={selectedInstance}
        />
      )}
      {activeRuntimeTab === "test" && (
        <AgentRuntimeTestPanel
          activeTestTab={activeTestTab}
          error={runner.error}
          input={input}
          inputError={inputError}
          onInputChange={handleInputChange}
          onTestTabChange={setActiveTestTab}
          response={runner.response}
          selectedInstance={selectedInstance}
        />
      )}
      {activeRuntimeTab === "evidence" && <AgentRuntimeEvidencePanel response={runner.response} />}
    </Drawer>
  );
}

function defaultAgentInput(agentKey: string, t: (key: string) => string) {
  if (agentKey === "image_generation") {
    return t("agentsDefaultInputImage");
  }
  if (agentKey === "video_generation") {
    return t("agentsDefaultInputVideo");
  }
  return t("agentsDefaultInputGeneral");
}
