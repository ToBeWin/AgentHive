import { useSyncExternalStore } from "react";
import type {
  AgentInstanceCreateRequest,
  AgentInstanceResponse,
  AgentInstanceUpdateRequest,
  AgentModuleActionResponse,
  AgentModuleCatalogEntry,
  ChannelCreateRequest,
  ChannelCreateResponse,
  ChannelResponse,
  ChannelStatus,
  DocumentUploadCompleteResponse,
  KnowledgeBaseCreateRequest,
  KnowledgeBaseResponse,
  KnowledgeDeleteResponse,
  KnowledgeDocumentResponse,
} from "../../lib/api";
import {
  PROTOTYPE_AGENT_INSTANCES,
  PROTOTYPE_AGENT_MODULES,
  PROTOTYPE_CHANNELS,
  PROTOTYPE_KNOWLEDGE_BASES,
  PROTOTYPE_KNOWLEDGE_DOCUMENTS,
  prototypeAgentCatalogFromModules,
  prototypeAgentInstance,
  prototypeAgentModuleAction,
  prototypeChannel,
  prototypeKnowledgeBase,
  prototypeKnowledgeDelete,
  prototypeKnowledgeUpload,
} from "./prototypeData";

type PrototypeSnapshot = {
  agentCatalog: ReturnType<typeof prototypeAgentCatalogFromModules>;
  agentInstances: AgentInstanceResponse[];
  agentModules: AgentModuleCatalogEntry[];
  channels: ChannelResponse[];
  knowledgeBases: KnowledgeBaseResponse[];
  knowledgeDocuments: KnowledgeDocumentResponse[];
};

let agentModules = cloneList(PROTOTYPE_AGENT_MODULES);
let agentInstances = cloneList(PROTOTYPE_AGENT_INSTANCES);
let knowledgeBases = cloneList(PROTOTYPE_KNOWLEDGE_BASES);
let knowledgeDocuments = cloneList(PROTOTYPE_KNOWLEDGE_DOCUMENTS);
let channels = cloneList(PROTOTYPE_CHANNELS);
let snapshot = createSnapshot();
const listeners = new Set<() => void>();

export function usePrototypeSnapshot() {
  return useSyncExternalStore(subscribePrototypeState, getPrototypeSnapshot, getPrototypeSnapshot);
}

export function getPrototypeSnapshot() {
  return snapshot;
}

export function resetPrototypeState() {
  agentModules = cloneList(PROTOTYPE_AGENT_MODULES);
  agentInstances = cloneList(PROTOTYPE_AGENT_INSTANCES);
  knowledgeBases = cloneList(PROTOTYPE_KNOWLEDGE_BASES);
  knowledgeDocuments = cloneList(PROTOTYPE_KNOWLEDGE_DOCUMENTS);
  channels = cloneList(PROTOTYPE_CHANNELS);
  emitPrototypeState();
}

export function createPrototypeAgentInstance(payload: AgentInstanceCreateRequest) {
  const created = prototypeAgentInstance(payload);
  agentInstances = [created, ...agentInstances];
  emitPrototypeState();
  return created;
}

export function updatePrototypeAgentInstance(agentId: string, payload: AgentInstanceUpdateRequest) {
  const current = agentInstances.find((instance) => instance.id === agentId) ?? agentInstances[0];
  const updated: AgentInstanceResponse = {
    ...current,
    config: Object.hasOwn(payload, "config") ? (payload.config ?? {}) : current.config,
    department_id: Object.hasOwn(payload, "department_id") ? (payload.department_id ?? null) : current.department_id,
    description: Object.hasOwn(payload, "description") ? (payload.description ?? null) : current.description,
    metadata: Object.hasOwn(payload, "metadata") ? (payload.metadata ?? {}) : current.metadata,
    model_key: Object.hasOwn(payload, "model_key") ? (payload.model_key ?? null) : current.model_key,
    model_routing_key: Object.hasOwn(payload, "model_routing_key")
      ? (payload.model_routing_key ?? null)
      : current.model_routing_key,
    name: payload.name ?? current.name,
    owner_user_id: Object.hasOwn(payload, "owner_user_id") ? (payload.owner_user_id ?? null) : current.owner_user_id,
    status: payload.status ?? current.status,
    system_prompt: Object.hasOwn(payload, "system_prompt") ? (payload.system_prompt ?? null) : current.system_prompt,
    updated_at: new Date().toISOString(),
    visibility: payload.visibility ?? current.visibility,
  };
  agentInstances = agentInstances.map((instance) => (instance.id === agentId ? updated : instance));
  emitPrototypeState();
  return updated;
}

export function runPrototypeAgentModuleAction(
  moduleId: string,
  action: "install" | "enable" | "disable",
): AgentModuleActionResponse {
  const response = prototypeAgentModuleAction(moduleId, action);
  agentModules = recalculateModuleDependencies(
    agentModules.map((module) => {
      if (module.id !== moduleId || !module.licensed || module.missing_features.length > 0) {
        return module;
      }
      if (action === "install") {
        return { ...module, enabled: false, installed: true, state: "installed" };
      }
      if (action === "enable") {
        return { ...module, enabled: true, installed: true, state: "enabled" };
      }
      return { ...module, enabled: false, installed: true, state: "disabled" };
    }),
  );
  emitPrototypeState();
  return response;
}

export function createPrototypeKnowledgeBase(payload: KnowledgeBaseCreateRequest) {
  const created = prototypeKnowledgeBase(payload);
  knowledgeBases = [created, ...knowledgeBases];
  emitPrototypeState();
  return created;
}

export function uploadPrototypeKnowledgeDocument(baseId: string, file: File): DocumentUploadCompleteResponse {
  const response = prototypeKnowledgeUpload(baseId, file);
  knowledgeDocuments = [response.document, ...knowledgeDocuments];
  knowledgeBases = knowledgeBases.map((base) =>
    base.id === baseId
      ? {
          ...base,
          document_count: knowledgeDocuments.filter((document) => document.knowledge_base_id === baseId).length,
          updated_at: response.document.updated_at,
        }
      : base,
  );
  emitPrototypeState();
  return response;
}

export function deletePrototypeKnowledgeBase(baseId: string): KnowledgeDeleteResponse {
  const response = prototypeKnowledgeDelete(baseId, "base");
  knowledgeBases = knowledgeBases.filter((base) => base.id !== baseId);
  knowledgeDocuments = knowledgeDocuments.filter((document) => document.knowledge_base_id !== baseId);
  emitPrototypeState();
  return response;
}

export function deletePrototypeKnowledgeDocument(baseId: string, documentId: string): KnowledgeDeleteResponse {
  const response = prototypeKnowledgeDelete(documentId, "document");
  knowledgeDocuments = knowledgeDocuments.filter((document) => document.id !== documentId);
  knowledgeBases = knowledgeBases.map((base) =>
    base.id === baseId
      ? {
          ...base,
          document_count: knowledgeDocuments.filter((document) => document.knowledge_base_id === baseId).length,
          updated_at: new Date().toISOString(),
        }
      : base,
  );
  emitPrototypeState();
  return response;
}

export function reingestPrototypeKnowledgeDocument(
  baseId: string,
  documentId: string,
): DocumentUploadCompleteResponse | null {
  const now = new Date().toISOString();
  const document = knowledgeDocuments.find((item) => item.knowledge_base_id === baseId && item.id === documentId);
  if (!document) {
    return null;
  }
  const updatedDocument: KnowledgeDocumentResponse = {
    ...document,
    error_message: null,
    status: "indexed",
    updated_at: now,
  };
  knowledgeDocuments = knowledgeDocuments.map((item) => (item.id === documentId ? updatedDocument : item));
  knowledgeBases = knowledgeBases.map((base) => (base.id === baseId ? { ...base, updated_at: now } : base));
  emitPrototypeState();
  return {
    auto_ingest: true,
    diagnostics: { engine: "pgvector", prototype: true },
    document: updatedDocument,
    ingest_status: "indexed",
    message: "Document reindexed in Prototype Mode.",
  };
}

export function createPrototypeChannel(payload: ChannelCreateRequest): ChannelCreateResponse {
  const response = prototypeChannel(payload);
  channels = [response.channel, ...channels];
  emitPrototypeState();
  return response;
}

export function updatePrototypeChannelStatus(channelId: string, status: ChannelStatus): ChannelResponse {
  const now = new Date().toISOString();
  channels = channels.map((channel) => (channel.id === channelId ? { ...channel, status, updated_at: now } : channel));
  emitPrototypeState();
  return channels.find((channel) => channel.id === channelId) ?? channels[0];
}

function subscribePrototypeState(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function emitPrototypeState() {
  snapshot = createSnapshot();
  for (const listener of listeners) {
    listener();
  }
}

function createSnapshot(): PrototypeSnapshot {
  const currentAgentModules = cloneList(agentModules);
  return {
    agentCatalog: prototypeAgentCatalogFromModules(currentAgentModules),
    agentInstances: cloneList(agentInstances),
    agentModules: currentAgentModules,
    channels: cloneList(channels),
    knowledgeBases: cloneList(knowledgeBases),
    knowledgeDocuments: cloneList(knowledgeDocuments),
  };
}

function recalculateModuleDependencies(modules: AgentModuleCatalogEntry[]) {
  const enabledModuleIds = new Set(modules.filter((module) => module.enabled).map((module) => module.id));
  return modules.map((module) => ({
    ...module,
    missing_dependencies: module.dependencies.filter((dependency) => !enabledModuleIds.has(dependency)),
  }));
}

function cloneList<T>(items: T[]): T[] {
  return items.map((item) => ({ ...item }));
}
