import type { ChangeEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  useKnowledgeActions,
  useKnowledgeBases,
  useKnowledgeDocuments,
  useKnowledgeGovernanceTargets,
  useWorkbenchKnowledgeBases,
  useWorkbenchKnowledgeDocuments,
} from "../../hooks/useAdminData";
import type {
  AuthUser,
  DocumentUploadCompleteResponse,
  KnowledgeBaseResponse,
  KnowledgeDocumentResponse,
  RetrievalTestResponse,
  WorkbenchKnowledgeBaseResponse,
  WorkbenchKnowledgeDocumentResponse,
} from "../../lib/api";
import { canAccess } from "../../lib/permissions";
import type { KnowledgeBaseFormState } from "./KnowledgeBaseSidebar";

export type KnowledgePageTab = "handoff" | "documents" | "retrieval";
export type KnowledgeBaseListItem = KnowledgeBaseResponse | WorkbenchKnowledgeBaseResponse;
export type KnowledgeDocumentListItem = KnowledgeDocumentResponse | WorkbenchKnowledgeDocumentResponse;

const AGENT_TAB_REQUEST_KEY = "agenthive.agents.default_tab";
const AGENT_KNOWLEDGE_REQUEST_KEY = "agenthive.agents.default_knowledge_base_id";

function defaultKnowledgeBaseForm(): KnowledgeBaseFormState {
  return {
    departmentIds: [],
    description: "Private enterprise knowledge for AgentHive RAG.",
    name: "Customer Support Knowledge",
    ragEngine: "ragflow",
    tags: "support, internal",
    visibility: "tenant",
  };
}

export function useKnowledgePageController({
  isPrototype = false,
  onNavigate,
  user = null,
}: {
  isPrototype?: boolean;
  onNavigate?: (pageId: "agents") => void;
  user?: AuthUser | null;
}) {
  const canWriteKnowledge = isPrototype || canAccess(user, ["knowledge:write"]);
  const canReadKnowledge = isPrototype || canAccess(user, ["knowledge:read", "knowledge:write"]);
  const [activeTab, setActiveTab] = useState<KnowledgePageTab>("documents");
  const {
    data: adminBases,
    error: adminBasesError,
    loading: adminBasesLoading,
    refetch: refetchAdminBases,
  } = useKnowledgeBases({ enabled: canWriteKnowledge, fallbackOnError: isPrototype });
  const {
    data: workbenchBases,
    error: workbenchBasesError,
    loading: workbenchBasesLoading,
    refetch: refetchWorkbenchBases,
  } = useWorkbenchKnowledgeBases({
    enabled: canReadKnowledge && !canWriteKnowledge,
    fallbackOnError: isPrototype,
  });
  const { data: governanceTargets } = useKnowledgeGovernanceTargets({
    enabled: canWriteKnowledge,
    fallbackOnError: isPrototype,
  });
  const {
    createKnowledgeBase,
    deleteKnowledgeBase,
    deleteKnowledgeDocument,
    deletingBaseId,
    deletingDocumentId,
    error: actionError,
    message: actionMessage,
    reingestKnowledgeDocument,
    reingestingDocumentId,
    runRetrievalTest,
    saving,
    testing,
    uploadKnowledgeDocument,
    uploading,
  } = useKnowledgeActions({ fallbackOnError: isPrototype });
  const baseList: KnowledgeBaseListItem[] = canWriteKnowledge ? (adminBases ?? []) : (workbenchBases ?? []);
  const basesError = canWriteKnowledge ? adminBasesError : workbenchBasesError;
  const basesLoading = canWriteKnowledge ? adminBasesLoading : workbenchBasesLoading;
  const refetchBases = canWriteKnowledge ? refetchAdminBases : refetchWorkbenchBases;
  const [selectedBaseId, setSelectedBaseId] = useState<string | null>(null);
  const selectedBase = baseList.find((base) => base.id === selectedBaseId) ?? baseList[0] ?? null;
  const {
    data: adminDocuments,
    error: adminDocumentsError,
    loading: adminDocumentsLoading,
    refetch: refetchAdminDocuments,
  } = useKnowledgeDocuments(selectedBase?.id ?? null, {
    enabled: canWriteKnowledge,
    fallbackOnError: isPrototype,
  });
  const {
    data: workbenchDocuments,
    error: workbenchDocumentsError,
    loading: workbenchDocumentsLoading,
    refetch: refetchWorkbenchDocuments,
  } = useWorkbenchKnowledgeDocuments(selectedBase?.id ?? null, {
    enabled: canReadKnowledge && !canWriteKnowledge,
    fallbackOnError: isPrototype,
  });
  const documentList: KnowledgeDocumentListItem[] = canWriteKnowledge
    ? (adminDocuments ?? [])
    : (workbenchDocuments ?? []);
  const documentsError = canWriteKnowledge ? adminDocumentsError : workbenchDocumentsError;
  const documentsLoading = canWriteKnowledge ? adminDocumentsLoading : workbenchDocumentsLoading;
  const refetchDocuments = canWriteKnowledge ? refetchAdminDocuments : refetchWorkbenchDocuments;
  const [form, setForm] = useState<KnowledgeBaseFormState>(() => defaultKnowledgeBaseForm());
  const [retrievalQuery, setRetrievalQuery] = useState("How should the assistant answer policy questions?");
  const [retrievalTopK, setRetrievalTopK] = useState(5);
  const [retrievalResult, setRetrievalResult] = useState<RetrievalTestResponse | null>(null);
  const [uploadResult, setUploadResult] = useState<DocumentUploadCompleteResponse | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const departmentOptions = useMemo(
    () => (governanceTargets?.departments ?? []).map((target) => ({ id: target.id, label: target.label })),
    [governanceTargets],
  );

  useEffect(() => {
    if (!baseList.length) {
      setSelectedBaseId(null);
      return;
    }
    setSelectedBaseId((current) => {
      if (current && baseList.some((base) => base.id === current)) {
        return current;
      }
      return baseList[0].id;
    });
  }, [baseList]);

  useEffect(() => {
    if (!canWriteKnowledge && activeTab === "retrieval") {
      setActiveTab("documents");
    }
  }, [activeTab, canWriteKnowledge]);

  const handleCreateKnowledgeBase = async () => {
    if (!canWriteKnowledge) {
      return false;
    }
    const created = await createKnowledgeBase({
      department_ids: form.visibility === "department" ? form.departmentIds : [],
      description: form.description.trim() || null,
      metadata: {
        created_from: "admin_knowledge_page",
        deployment_mode: "private",
      },
      name: form.name.trim(),
      rag_engine: form.ragEngine,
      retrieval_config: {
        citation_required: true,
        metadata_filters: {},
        rerank_enabled: false,
        score_threshold: null,
        top_k: 5,
      },
      tags: form.tags
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
      visibility: form.visibility,
    });
    if (created) {
      setSelectedBaseId(created.id);
      setRetrievalResult(null);
      setForm(defaultKnowledgeBaseForm());
      await refetchBases();
      return true;
    }
    return false;
  };

  const handleRetrievalTest = async () => {
    if (!selectedBase || !retrievalQuery.trim()) {
      return;
    }
    const response = await runRetrievalTest(selectedBase.id, {
      filters: {},
      include_raw_chunks: false,
      query: retrievalQuery.trim(),
      rerank: false,
      score_threshold: null,
      top_k: Math.min(50, Math.max(1, retrievalTopK)),
    });
    if (response) {
      setRetrievalResult(response);
    }
  };

  const handlePickUploadFile = () => {
    if (!canWriteKnowledge || !selectedBase || uploading) {
      return;
    }
    fileInputRef.current?.click();
  };

  const handleUploadFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!canWriteKnowledge || !selectedBase || !file) {
      return;
    }
    const response = await uploadKnowledgeDocument(selectedBase.id, file);
    if (response) {
      setUploadResult(response);
      await Promise.all([refetchDocuments(), refetchBases()]);
    }
  };

  const handleUploadDocumentFile = async (file: File) => {
    if (!canWriteKnowledge || !selectedBase || uploading) {
      return;
    }
    const response = await uploadKnowledgeDocument(selectedBase.id, file);
    if (response) {
      setUploadResult(response);
      await Promise.all([refetchDocuments(), refetchBases()]);
    }
  };

  const handleDeleteKnowledgeBase = async (baseId: string) => {
    if (!canWriteKnowledge) {
      return;
    }
    const target = baseList.find((base) => base.id === baseId);
    if (!target) {
      return;
    }
    const response = await deleteKnowledgeBase(baseId);
    if (response) {
      setSelectedBaseId((current) => (current === baseId ? null : current));
      setRetrievalResult(null);
      setUploadResult(null);
      await refetchBases();
    }
  };

  const handleDeleteKnowledgeDocument = async (documentId: string) => {
    if (!canWriteKnowledge || !selectedBase) {
      return;
    }
    const response = await deleteKnowledgeDocument(selectedBase.id, documentId);
    if (response) {
      setRetrievalResult(null);
      setUploadResult(null);
      await Promise.all([refetchDocuments(), refetchBases()]);
    }
  };

  const handleReingestKnowledgeDocument = async (documentId: string) => {
    if (!canWriteKnowledge || !selectedBase) {
      return;
    }
    const response = await reingestKnowledgeDocument(selectedBase.id, documentId);
    if (response) {
      setUploadResult(response);
      setRetrievalResult(null);
      await Promise.all([refetchDocuments(), refetchBases()]);
    }
  };

  const handleSelectBase = (id: string) => {
    setSelectedBaseId(id);
    setRetrievalResult(null);
  };

  const handleOpenAgentBinding = () => {
    window.sessionStorage.setItem(AGENT_TAB_REQUEST_KEY, "instances");
    if (selectedBase) {
      window.sessionStorage.setItem(AGENT_KNOWLEDGE_REQUEST_KEY, selectedBase.id);
    }
    onNavigate?.("agents");
  };

  return {
    actionError,
    actionMessage,
    activeTab,
    baseList,
    basesError,
    basesLoading,
    canWriteKnowledge,
    deletingBaseId,
    deletingDocumentId,
    departmentOptions,
    documentList,
    documentsError,
    documentsLoading,
    fileInputRef,
    form,
    handleCreateKnowledgeBase,
    handleDeleteKnowledgeBase,
    handleDeleteKnowledgeDocument,
    handleOpenAgentBinding,
    handlePickUploadFile,
    handleReingestKnowledgeDocument,
    handleRetrievalTest,
    handleSelectBase,
    handleUploadDocumentFile,
    handleUploadFile,
    refetchBases,
    refetchDocuments,
    reingestingDocumentId,
    retrievalQuery,
    retrievalResult,
    retrievalTopK,
    resetKnowledgeBaseForm: () => setForm(defaultKnowledgeBaseForm()),
    saving,
    selectedBase,
    setActiveTab,
    setForm,
    setRetrievalQuery,
    setRetrievalTopK,
    testing,
    uploadResult,
    uploading,
  };
}
