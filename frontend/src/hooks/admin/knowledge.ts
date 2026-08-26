import { useCallback, useEffect, useRef, useState } from "react";
import { useToast } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import {
  adminApi,
  type DocumentUploadCompleteResponse,
  type KnowledgeBaseCreateRequest,
  type KnowledgeBaseResponse,
  type KnowledgeDocumentResponse,
  type KnowledgeGovernanceTargetsResponse,
  type RetrievalTestRequest,
  type RetrievalTestResponse,
  type WorkbenchKnowledgeBaseResponse,
  type WorkbenchKnowledgeDocumentResponse,
} from "../../lib/api";
import { PROTOTYPE_DEPARTMENT_ID, prototypeRetrievalTest } from "./prototypeData";
import {
  createPrototypeKnowledgeBase,
  deletePrototypeKnowledgeBase,
  deletePrototypeKnowledgeDocument,
  getPrototypeSnapshot,
  reingestPrototypeKnowledgeDocument,
  uploadPrototypeKnowledgeDocument,
  usePrototypeSnapshot,
} from "./prototypeState";
import { type AsyncState, errorToMessage, withRetry } from "./shared";

const PROTOTYPE_KNOWLEDGE_GOVERNANCE_TARGETS: KnowledgeGovernanceTargetsResponse = {
  departments: [
    {
      description: "Prototype department for private knowledge and Agent governance.",
      id: PROTOTYPE_DEPARTMENT_ID,
      label: "Customer Success",
      metadata: { parent_id: null, sort_order: 10 },
    },
  ],
};

function toWorkbenchKnowledgeBase(base: KnowledgeBaseResponse): WorkbenchKnowledgeBaseResponse {
  return {
    department_ids: base.department_ids,
    description: base.description,
    document_count: base.document_count,
    id: base.id,
    name: base.name,
    status: base.status,
    tags: base.tags,
    updated_at: base.updated_at,
    visibility: base.visibility,
  };
}

function toWorkbenchKnowledgeDocument(document: KnowledgeDocumentResponse): WorkbenchKnowledgeDocumentResponse {
  return {
    chunk_count: document.chunk_count,
    content_type: document.content_type,
    filename: document.filename,
    id: document.id,
    knowledge_base_id: document.knowledge_base_id,
    size_bytes: document.size_bytes,
    source: document.source,
    status: document.status,
    updated_at: document.updated_at,
  };
}

export function useKnowledgeGovernanceTargets(options: { enabled?: boolean; fallbackOnError?: boolean } = {}) {
  const enabled = options.enabled !== false;
  const fallbackOnError = options.fallbackOnError === true;
  const [state, setState] = useState<AsyncState<KnowledgeGovernanceTargetsResponse>>({
    data: null,
    error: null,
    loading: enabled,
  });

  const load = useCallback(async () => {
    if (!enabled) {
      setState({ data: null, error: null, loading: false });
      return;
    }
    setState((current) => ({ ...current, error: null, loading: true }));
    if (fallbackOnError) {
      setState({ data: PROTOTYPE_KNOWLEDGE_GOVERNANCE_TARGETS, error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getKnowledgeGovernanceTargets());
      setState({ data, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [enabled, fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!enabled) {
    return { data: null, error: null, loading: false, refetch: load };
  }

  if (fallbackOnError) {
    return { data: PROTOTYPE_KNOWLEDGE_GOVERNANCE_TARGETS, error: null, loading: false, refetch: load };
  }

  return { ...state, refetch: load };
}

export function useKnowledgeBases(options: { enabled?: boolean; fallbackOnError?: boolean } = {}) {
  const enabled = options.enabled !== false;
  const fallbackOnError = options.fallbackOnError === true;
  const prototypeSnapshot = usePrototypeSnapshot();
  const [state, setState] = useState<AsyncState<KnowledgeBaseResponse[]>>({
    data: null,
    error: null,
    loading: enabled,
  });

  const load = useCallback(async () => {
    if (!enabled) {
      setState({ data: [], error: null, loading: false });
      return;
    }
    setState((current) => ({ ...current, error: null, loading: true }));
    if (fallbackOnError) {
      setState({ data: getPrototypeSnapshot().knowledgeBases, error: null, loading: false });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getKnowledgeBases());
      setState({ data: data.bases, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [enabled, fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!enabled) {
    return { data: [], error: null, loading: false, refetch: load };
  }

  if (fallbackOnError) {
    return { data: prototypeSnapshot.knowledgeBases, error: null, loading: false, refetch: load };
  }

  return { ...state, refetch: load };
}

export function useWorkbenchKnowledgeBases(options: { enabled?: boolean; fallbackOnError?: boolean } = {}) {
  const enabled = options.enabled !== false;
  const fallbackOnError = options.fallbackOnError === true;
  const prototypeSnapshot = usePrototypeSnapshot();
  const [state, setState] = useState<AsyncState<WorkbenchKnowledgeBaseResponse[]>>({
    data: null,
    error: null,
    loading: enabled,
  });

  const load = useCallback(async () => {
    if (!enabled) {
      setState({ data: [], error: null, loading: false });
      return;
    }
    setState((current) => ({ ...current, error: null, loading: true }));
    if (fallbackOnError) {
      setState({
        data: getPrototypeSnapshot().knowledgeBases.map(toWorkbenchKnowledgeBase),
        error: null,
        loading: false,
      });
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getWorkbenchKnowledgeBases());
      setState({ data: data.bases, error: null, loading: false });
    } catch (error) {
      setState({ data: null, error: errorToMessage(error), loading: false });
    }
  }, [enabled, fallbackOnError]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!enabled) {
    return { data: [], error: null, loading: false, refetch: load };
  }

  if (fallbackOnError) {
    return {
      data: prototypeSnapshot.knowledgeBases.map(toWorkbenchKnowledgeBase),
      error: null,
      loading: false,
      refetch: load,
    };
  }

  return { ...state, refetch: load };
}

export function useKnowledgeDocuments(
  baseId: string | null,
  options: { enabled?: boolean; fallbackOnError?: boolean } = {},
) {
  const latestRequestId = useRef(0);
  const enabled = options.enabled !== false;
  const fallbackOnError = options.fallbackOnError === true;
  const prototypeSnapshot = usePrototypeSnapshot();
  const [state, setState] = useState<AsyncState<KnowledgeDocumentResponse[]>>({
    data: null,
    error: null,
    loading: false,
  });

  const load = useCallback(async () => {
    const requestId = ++latestRequestId.current;
    if (!enabled || !baseId) {
      if (requestId === latestRequestId.current) {
        setState({ data: [], error: null, loading: false });
      }
      return;
    }
    setState((current) => ({ ...current, error: null, loading: true }));
    if (fallbackOnError) {
      const documents = getPrototypeSnapshot().knowledgeDocuments;
      if (requestId === latestRequestId.current) {
        setState({
          data: documents.filter((document) => document.knowledge_base_id === baseId),
          error: null,
          loading: false,
        });
      }
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getKnowledgeDocuments(baseId));
      if (requestId === latestRequestId.current) {
        setState({ data: data.documents, error: null, loading: false });
      }
    } catch (error) {
      if (requestId === latestRequestId.current) {
        setState({ data: null, error: errorToMessage(error), loading: false });
      }
    }
  }, [baseId, enabled, fallbackOnError]);

  useEffect(() => {
    void load();
    return () => {
      latestRequestId.current += 1;
    };
  }, [load]);

  if (!enabled) {
    return { data: [], error: null, loading: false, refetch: load };
  }

  if (fallbackOnError) {
    return {
      data: baseId
        ? prototypeSnapshot.knowledgeDocuments.filter((document) => document.knowledge_base_id === baseId)
        : [],
      error: null,
      loading: false,
      refetch: load,
    };
  }

  return { ...state, refetch: load };
}

export function useWorkbenchKnowledgeDocuments(
  baseId: string | null,
  options: { enabled?: boolean; fallbackOnError?: boolean } = {},
) {
  const latestRequestId = useRef(0);
  const enabled = options.enabled !== false;
  const fallbackOnError = options.fallbackOnError === true;
  const prototypeSnapshot = usePrototypeSnapshot();
  const [state, setState] = useState<AsyncState<WorkbenchKnowledgeDocumentResponse[]>>({
    data: null,
    error: null,
    loading: false,
  });

  const load = useCallback(async () => {
    const requestId = ++latestRequestId.current;
    if (!enabled || !baseId) {
      if (requestId === latestRequestId.current) {
        setState({ data: [], error: null, loading: false });
      }
      return;
    }
    setState((current) => ({ ...current, error: null, loading: true }));
    if (fallbackOnError) {
      if (requestId === latestRequestId.current) {
        setState({
          data: getPrototypeSnapshot()
            .knowledgeDocuments.filter((document) => document.knowledge_base_id === baseId)
            .map(toWorkbenchKnowledgeDocument),
          error: null,
          loading: false,
        });
      }
      return;
    }
    try {
      const data = await withRetry(() => adminApi.getWorkbenchKnowledgeDocuments(baseId));
      if (requestId === latestRequestId.current) {
        setState({ data: data.documents, error: null, loading: false });
      }
    } catch (error) {
      if (requestId === latestRequestId.current) {
        setState({ data: null, error: errorToMessage(error), loading: false });
      }
    }
  }, [baseId, enabled, fallbackOnError]);

  useEffect(() => {
    void load();
    return () => {
      latestRequestId.current += 1;
    };
  }, [load]);

  if (!enabled) {
    return { data: [], error: null, loading: false, refetch: load };
  }

  if (fallbackOnError) {
    return {
      data: baseId
        ? prototypeSnapshot.knowledgeDocuments
            .filter((document) => document.knowledge_base_id === baseId)
            .map(toWorkbenchKnowledgeDocument)
        : [],
      error: null,
      loading: false,
      refetch: load,
    };
  }

  return { ...state, refetch: load };
}

export function useKnowledgeActions(options: { fallbackOnError?: boolean } = {}) {
  const { t } = useLocale();
  const { showToast } = useToast();
  const fallbackOnError = options.fallbackOnError === true;
  const [saving, setSaving] = useState(false);
  const [deletingBaseId, setDeletingBaseId] = useState<string | null>(null);
  const [deletingDocumentId, setDeletingDocumentId] = useState<string | null>(null);
  const [reingestingDocumentId, setReingestingDocumentId] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const createKnowledgeBase = useCallback(
    async (payload: KnowledgeBaseCreateRequest) => {
      setSaving(true);
      setMessage(null);
      setError(null);
      if (fallbackOnError) {
        const response = createPrototypeKnowledgeBase(payload);
        setSaving(false);
        const successMessage = t("knowledgeBaseCreated").replace("{{name}}", response.name);
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      }
      try {
        const response = await adminApi.createKnowledgeBase(payload);
        const successMessage = t("knowledgeBaseCreated").replace("{{name}}", response.name);
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setSaving(false);
      }
    },
    [fallbackOnError, showToast, t],
  );

  const uploadKnowledgeDocument = useCallback(
    async (baseId: string, file: File): Promise<DocumentUploadCompleteResponse | null> => {
      setUploading(true);
      setMessage(null);
      setError(null);
      if (fallbackOnError) {
        const response = uploadPrototypeKnowledgeDocument(baseId, file);
        setUploading(false);
        const successMessage =
          response.message || t("knowledgeDocumentUploaded").replace("{{name}}", response.document.filename);
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      }
      try {
        const response = await adminApi.uploadKnowledgeDocument(baseId, file, true);
        const successMessage =
          response.message || t("knowledgeDocumentUploaded").replace("{{name}}", response.document.filename);
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setUploading(false);
      }
    },
    [fallbackOnError, showToast, t],
  );

  const deleteKnowledgeBase = useCallback(
    async (baseId: string) => {
      setDeletingBaseId(baseId);
      setMessage(null);
      setError(null);
      if (fallbackOnError) {
        const response = deletePrototypeKnowledgeBase(baseId);
        setDeletingBaseId(null);
        const successMessage = response.message || t("knowledgeBaseDeleted");
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      }
      try {
        const response = await adminApi.deleteKnowledgeBase(baseId);
        const successMessage = response.message || t("knowledgeBaseDeleted");
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setDeletingBaseId(null);
      }
    },
    [fallbackOnError, showToast, t],
  );

  const deleteKnowledgeDocument = useCallback(
    async (baseId: string, documentId: string) => {
      setDeletingDocumentId(documentId);
      setMessage(null);
      setError(null);
      if (fallbackOnError) {
        const response = deletePrototypeKnowledgeDocument(baseId, documentId);
        setDeletingDocumentId(null);
        const successMessage = response.message || t("knowledgeDocumentDeleted");
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      }
      try {
        const response = await adminApi.deleteKnowledgeDocument(baseId, documentId);
        const successMessage = response.message || t("knowledgeDocumentDeleted");
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setDeletingDocumentId(null);
      }
    },
    [fallbackOnError, showToast, t],
  );

  const reingestKnowledgeDocument = useCallback(
    async (baseId: string, documentId: string): Promise<DocumentUploadCompleteResponse | null> => {
      setReingestingDocumentId(documentId);
      setMessage(null);
      setError(null);
      if (fallbackOnError) {
        const response = reingestPrototypeKnowledgeDocument(baseId, documentId);
        if (!response) {
          setReingestingDocumentId(null);
          const errorMessage = t("knowledgeDocumentReingested");
          setError(errorMessage);
          showToast(errorMessage, "error");
          return null;
        }
        setReingestingDocumentId(null);
        const successMessage = response.message || t("knowledgeDocumentReingested");
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      }
      try {
        const response = await adminApi.reingestKnowledgeDocument(baseId, documentId);
        const successMessage = response.message || t("knowledgeDocumentReingested");
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setReingestingDocumentId(null);
      }
    },
    [fallbackOnError, showToast, t],
  );

  const runRetrievalTest = useCallback(
    async (baseId: string, payload: RetrievalTestRequest) => {
      setTesting(true);
      setMessage(null);
      setError(null);
      if (fallbackOnError) {
        const response = prototypeRetrievalTest(baseId, payload);
        setTesting(false);
        const successMessage = t("knowledgeRetrievedSources").replace("{{count}}", String(response.results.length));
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      }
      try {
        const response: RetrievalTestResponse = await adminApi.runRetrievalTest(baseId, payload);
        const successMessage = t("knowledgeRetrievedSources").replace("{{count}}", String(response.results.length));
        setMessage(successMessage);
        showToast(successMessage, "success");
        return response;
      } catch (caught) {
        const errorMessage = errorToMessage(caught);
        setError(errorMessage);
        showToast(errorMessage, "error");
        return null;
      } finally {
        setTesting(false);
      }
    },
    [fallbackOnError, showToast, t],
  );

  return {
    createKnowledgeBase,
    deleteKnowledgeBase,
    deleteKnowledgeDocument,
    deletingBaseId,
    deletingDocumentId,
    error,
    message,
    reingestKnowledgeDocument,
    reingestingDocumentId,
    runRetrievalTest,
    saving,
    testing,
    uploading,
    uploadKnowledgeDocument,
  };
}
