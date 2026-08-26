import type { Locale } from "../../i18n";
import { agentDisplayDescription, agentDisplayName } from "../../lib/agentDisplay";
import type { AgentCatalogEntryResponse, AgentInstanceResponse } from "../../lib/api";

export interface AgentKnowledgeBaseOption {
  id: string;
  name: string;
  rag_engine: string;
}

export interface AgentModelDeploymentOption {
  id: string;
  label: string;
  routing_key: string;
}

export interface AgentInstanceFormState {
  name: string;
  slug: string;
  agentKey: string;
  description: string;
  visibility: "tenant" | "department" | "private";
  modelRoutingKey: string;
  modelKey: string;
  knowledgeBaseIds: string[];
}

export interface KnowledgeBaseBindingLabel {
  id: string;
  label: string;
}

export const emptyAgentInstanceForm: AgentInstanceFormState = {
  agentKey: "",
  description: "",
  modelKey: "",
  modelRoutingKey: "default-chat",
  name: "",
  slug: "",
  visibility: "tenant",
  knowledgeBaseIds: [],
};

export function defaultInstanceName(catalog: AgentCatalogEntryResponse[], agentKey: string, locale: Locale = "en-US") {
  const agent = catalog.find((item) => item.agent_key === agentKey);
  if (!agent) {
    return "";
  }
  return locale === "zh-CN" ? `${agentDisplayName(agent, locale)}实例` : `${agentDisplayName(agent, locale)} Instance`;
}

export function defaultInstanceDescription(
  catalog: AgentCatalogEntryResponse[],
  agentKey: string,
  locale: Locale = "en-US",
) {
  const agent = catalog.find((item) => item.agent_key === agentKey);
  return agent ? (agentDisplayDescription(agent, locale) ?? "") : "";
}

export function knowledgeBaseIdsFromConfig(config: Record<string, unknown> | undefined): string[] {
  const refs: string[] = [];
  const singleId = config?.knowledge_base_id;
  if (typeof singleId === "string" && singleId.trim()) {
    refs.push(singleId.trim());
  }
  const rawIds = config?.knowledge_base_ids;
  if (!Array.isArray(rawIds)) {
    return refs;
  }
  for (const item of rawIds) {
    if (typeof item === "string" && item.trim() && !refs.includes(item.trim())) {
      refs.push(item.trim());
    }
  }
  return refs;
}

export function knowledgeBaseBindingsForInstance(
  instance: AgentInstanceResponse,
  knowledgeBases: AgentKnowledgeBaseOption[],
): KnowledgeBaseBindingLabel[] {
  const baseById = new Map(knowledgeBases.map((base) => [base.id, base]));
  return knowledgeBaseIdsFromConfig(instance.config).map((id) => {
    const base = baseById.get(id);
    return {
      id,
      label: base ? `${base.name} · ${base.rag_engine}` : id,
    };
  });
}

export function knowledgeBaseLabelsForInstance(
  instance: AgentInstanceResponse,
  knowledgeBases: AgentKnowledgeBaseOption[],
): string[] {
  return knowledgeBaseBindingsForInstance(instance, knowledgeBases).map((binding) => binding.label);
}
