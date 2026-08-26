import { apiDelete, apiGet, apiPost, apiPostForm } from "./core";

export type RAGEngineType = "ragflow" | "pgvector";
export type KnowledgeBaseStatus = "active" | "archived";
export type KnowledgeBaseVisibility = "private" | "department" | "tenant";
export type KnowledgeDocumentStatus = "pending_upload" | "uploaded" | "ingesting" | "indexed" | "failed" | "deleted";
export type KnowledgeDocumentSource = "api_upload" | "channel_attachment" | "internal_import";

export interface RetrievalConfig {
  top_k: number;
  score_threshold: number | null;
  rerank_enabled: boolean;
  citation_required: boolean;
  metadata_filters: Record<string, unknown>;
}

export interface KnowledgeBaseCreateRequest {
  name: string;
  description?: string | null;
  visibility: KnowledgeBaseVisibility;
  department_ids?: string[];
  rag_engine: RAGEngineType;
  embedding_model_key?: string | null;
  retrieval_config?: RetrievalConfig;
  tags?: string[];
  metadata?: Record<string, unknown>;
}

export interface KnowledgeBaseResponse {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  visibility: KnowledgeBaseVisibility;
  department_ids: string[];
  rag_engine: RAGEngineType;
  embedding_model_key: string | null;
  retrieval_config: RetrievalConfig;
  status: KnowledgeBaseStatus;
  document_count: number;
  tags: string[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeBaseListResponse {
  bases: KnowledgeBaseResponse[];
}

export interface WorkbenchKnowledgeBaseResponse {
  id: string;
  name: string;
  description: string | null;
  visibility: KnowledgeBaseVisibility;
  department_ids: string[];
  status: KnowledgeBaseStatus;
  document_count: number;
  tags: string[];
  updated_at: string;
}

export interface WorkbenchKnowledgeBaseListResponse {
  bases: WorkbenchKnowledgeBaseResponse[];
}

export interface KnowledgeGovernanceTargetItem {
  id: string;
  label: string;
  description: string | null;
  metadata: Record<string, unknown>;
}

export interface KnowledgeGovernanceTargetsResponse {
  departments: KnowledgeGovernanceTargetItem[];
}

export interface KnowledgeDocumentResponse {
  id: string;
  knowledge_base_id: string;
  tenant_id: string;
  filename: string;
  content_type: string | null;
  size_bytes: number | null;
  checksum_sha256: string | null;
  source: KnowledgeDocumentSource;
  status: KnowledgeDocumentStatus;
  storage_bucket: string;
  storage_object_key: string;
  rag_document_id: string | null;
  chunk_count: number;
  error_message: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDocumentListResponse {
  documents: KnowledgeDocumentResponse[];
}

export interface WorkbenchKnowledgeDocumentResponse {
  id: string;
  knowledge_base_id: string;
  filename: string;
  content_type: string | null;
  size_bytes: number | null;
  source: KnowledgeDocumentSource;
  status: KnowledgeDocumentStatus;
  chunk_count: number;
  updated_at: string;
}

export interface WorkbenchKnowledgeDocumentListResponse {
  documents: WorkbenchKnowledgeDocumentResponse[];
}

export interface KnowledgeDeleteResponse {
  id: string;
  deleted: boolean;
  message: string;
  diagnostics: Record<string, unknown>;
}

export interface RetrievalTestRequest {
  query: string;
  top_k: number;
  score_threshold?: number | null;
  filters?: Record<string, unknown>;
  include_raw_chunks?: boolean;
  rerank?: boolean;
}

export interface RetrievalSourceResponse {
  chunk_id: string;
  document_id: string | null;
  source_name: string | null;
  score: number | null;
  text: string;
  metadata: Record<string, unknown>;
}

export interface RetrievalTestResponse {
  knowledge_base_id: string;
  query: string;
  engine: RAGEngineType;
  elapsed_ms: number;
  results: RetrievalSourceResponse[];
  diagnostics: Record<string, unknown>;
  checked_at: string;
}

export interface DocumentUploadCompleteRequest {
  etag?: string | null;
  size_bytes?: number | null;
  checksum_sha256?: string | null;
  auto_ingest: boolean;
  metadata?: Record<string, unknown>;
}

export interface DocumentUploadCompleteResponse {
  document: KnowledgeDocumentResponse;
  auto_ingest: boolean;
  ingest_status: KnowledgeDocumentStatus | null;
  message: string;
  diagnostics: Record<string, unknown>;
}

export const knowledgeApi = {
  getKnowledgeGovernanceTargets: () =>
    apiGet<KnowledgeGovernanceTargetsResponse>("/api/v1/knowledge/governance-targets"),
  getKnowledgeBases: () => apiGet<KnowledgeBaseListResponse>("/api/v1/knowledge/bases"),
  getWorkbenchKnowledgeBases: () => apiGet<WorkbenchKnowledgeBaseListResponse>("/api/v1/knowledge/workbench/bases"),
  createKnowledgeBase: (payload: KnowledgeBaseCreateRequest) =>
    apiPost<KnowledgeBaseResponse, KnowledgeBaseCreateRequest>("/api/v1/knowledge/bases", payload),
  deleteKnowledgeBase: (baseId: string) => apiDelete<KnowledgeDeleteResponse>(`/api/v1/knowledge/bases/${baseId}`),
  getKnowledgeDocuments: (baseId: string) =>
    apiGet<KnowledgeDocumentListResponse>(`/api/v1/knowledge/bases/${baseId}/documents`),
  getWorkbenchKnowledgeDocuments: (baseId: string) =>
    apiGet<WorkbenchKnowledgeDocumentListResponse>(`/api/v1/knowledge/workbench/bases/${baseId}/documents`),
  deleteKnowledgeDocument: (baseId: string, documentId: string) =>
    apiDelete<KnowledgeDeleteResponse>(`/api/v1/knowledge/bases/${baseId}/documents/${documentId}`),
  reingestKnowledgeDocument: (baseId: string, documentId: string) =>
    apiPost<DocumentUploadCompleteResponse, Record<string, never>>(
      `/api/v1/knowledge/bases/${baseId}/documents/${documentId}/reingest`,
      {},
    ),
  uploadKnowledgeDocument: (baseId: string, file: File, autoIngest = true) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("auto_ingest", String(autoIngest));
    return apiPostForm<DocumentUploadCompleteResponse>(`/api/v1/knowledge/bases/${baseId}/documents/upload`, formData);
  },
  completeKnowledgeDocumentUpload: (baseId: string, documentId: string, payload: DocumentUploadCompleteRequest) =>
    apiPost<DocumentUploadCompleteResponse, DocumentUploadCompleteRequest>(
      `/api/v1/knowledge/bases/${baseId}/documents/${documentId}/complete-upload`,
      payload,
    ),
  runRetrievalTest: (baseId: string, payload: RetrievalTestRequest) =>
    apiPost<RetrievalTestResponse, RetrievalTestRequest>(`/api/v1/knowledge/bases/${baseId}/retrieval-test`, payload),
};
