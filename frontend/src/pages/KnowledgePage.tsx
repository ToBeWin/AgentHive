import { useEffect, useState } from "react";
import { PageTabs } from "../components/app-ui";
import type { WorkspaceId } from "../data";
import { useLocale } from "../i18n-context";
import type { AuthUser, KnowledgeDocumentResponse } from "../lib/api";
import { showDeliveryDiagnostics } from "../lib/deliveryDiagnostics";
import { KnowledgeBaseCreateDrawer } from "./knowledge/KnowledgeBaseCreateDrawer";
import { KnowledgeBaseSidebar } from "./knowledge/KnowledgeBaseSidebar";
import { KnowledgeDocumentReadinessPanel } from "./knowledge/KnowledgeDocumentReadinessPanel";
import { KnowledgeDocumentsPanel } from "./knowledge/KnowledgeDocumentsPanel";
import { KnowledgeRetrievalPanel } from "./knowledge/KnowledgeRetrievalPanel";
import { useKnowledgePageController } from "./knowledge/useKnowledgePageController";

export function KnowledgePage({
  activeWorkspace = "admin",
  isPrototype = false,
  onNavigate,
  user = null,
}: {
  activeWorkspace?: WorkspaceId;
  isPrototype?: boolean;
  onNavigate?: (pageId: "agents") => void;
  user?: AuthUser | null;
}) {
  const { t } = useLocale();
  const knowledge = useKnowledgePageController({ isPrototype, onNavigate, user });
  const showDiagnostics = showDeliveryDiagnostics(activeWorkspace);
  const isEmployeeView = activeWorkspace === "user" && !knowledge.canWriteKnowledge;
  const adminDocuments = knowledge.canWriteKnowledge ? (knowledge.documentList as KnowledgeDocumentResponse[]) : [];
  const adminSelectedBase =
    knowledge.canWriteKnowledge && knowledge.selectedBase && "rag_engine" in knowledge.selectedBase
      ? knowledge.selectedBase
      : null;
  const [createDrawerOpen, setCreateDrawerOpen] = useState(false);
  const openCreateDrawer = () => {
    knowledge.resetKnowledgeBaseForm();
    setCreateDrawerOpen(true);
  };
  const createKnowledgeBaseAndClose = async () => {
    const created = await knowledge.handleCreateKnowledgeBase();
    if (created) {
      setCreateDrawerOpen(false);
    }
    return created;
  };
  const tabs = [
    ...(knowledge.canWriteKnowledge && showDiagnostics
      ? [{ id: "handoff" as const, label: t("knowledgeTabHandoff"), description: t("knowledgeTabHandoffDesc") }]
      : []),
    { id: "documents" as const, label: t("knowledgeTabDocuments"), description: t("knowledgeTabDocumentsDesc") },
    ...(knowledge.canWriteKnowledge
      ? [{ id: "retrieval" as const, label: t("knowledgeTabRetrieval"), description: t("knowledgeTabRetrievalDesc") }]
      : []),
  ];

  useEffect(() => {
    if (!showDiagnostics && knowledge.activeTab === "handoff") {
      knowledge.setActiveTab("documents");
    }
  }, [knowledge.activeTab, knowledge.setActiveTab, showDiagnostics]);

  return (
    <section className="page kb-layout">
      <KnowledgeBaseSidebar
        baseList={knowledge.baseList}
        basesError={knowledge.basesError}
        basesLoading={knowledge.basesLoading}
        canWrite={knowledge.canWriteKnowledge}
        titleKey={isEmployeeView ? "knowledgeVisibleResourcesTitle" : "knowledgeBasesTitle"}
        countLabelKey={isEmployeeView ? "knowledgeVisibleResourcesCount" : "knowledgeSidebarBases"}
        onCreateClick={openCreateDrawer}
        onDeleteKnowledgeBase={knowledge.handleDeleteKnowledgeBase}
        onSelectBase={knowledge.handleSelectBase}
        refetchBases={knowledge.refetchBases}
        deletingBaseId={knowledge.deletingBaseId}
        selectedBaseId={knowledge.selectedBase?.id ?? null}
      />
      <div className="kb-workspace">
        <PageTabs active={knowledge.activeTab} onChange={knowledge.setActiveTab} tabs={tabs} />
        {knowledge.canWriteKnowledge && knowledge.activeTab === "handoff" && (
          <KnowledgeDocumentReadinessPanel
            actionError={knowledge.actionError}
            documents={adminDocuments}
            onOpenAgentBinding={knowledge.handleOpenAgentBinding}
            onOpenDocuments={() => knowledge.setActiveTab("documents")}
            onOpenRetrieval={() => knowledge.setActiveTab("retrieval")}
            onPickUploadFile={knowledge.handlePickUploadFile}
            retrievalResult={knowledge.retrievalResult}
            selectedBase={adminSelectedBase}
            uploadResult={knowledge.uploadResult}
          />
        )}
        {knowledge.activeTab === "documents" && (
          <KnowledgeDocumentsPanel
            canWrite={knowledge.canWriteKnowledge}
            deletingDocumentId={knowledge.deletingDocumentId}
            documentList={knowledge.documentList}
            documentsError={knowledge.documentsError}
            documentsLoading={knowledge.documentsLoading}
            employeeView={isEmployeeView}
            fileInputRef={knowledge.fileInputRef}
            onDeleteDocument={knowledge.handleDeleteKnowledgeDocument}
            onOpenAgentBinding={knowledge.handleOpenAgentBinding}
            onOpenRetrieval={() => knowledge.setActiveTab("retrieval")}
            onPickUploadFile={knowledge.handlePickUploadFile}
            onReingestDocument={knowledge.handleReingestKnowledgeDocument}
            onUploadDocumentFile={knowledge.handleUploadDocumentFile}
            onUploadFile={knowledge.handleUploadFile}
            refetchDocuments={knowledge.refetchDocuments}
            reingestingDocumentId={knowledge.reingestingDocumentId}
            selectedBase={knowledge.selectedBase}
            uploading={knowledge.uploading}
          />
        )}
        {knowledge.canWriteKnowledge && knowledge.activeTab === "retrieval" && (
          <KnowledgeRetrievalPanel
            actionError={knowledge.actionError}
            onRetrievalQueryChange={knowledge.setRetrievalQuery}
            onRetrievalTest={knowledge.handleRetrievalTest}
            onRetrievalTopKChange={knowledge.setRetrievalTopK}
            retrievalQuery={knowledge.retrievalQuery}
            retrievalResult={knowledge.retrievalResult}
            retrievalTopK={knowledge.retrievalTopK}
            selectedBase={
              knowledge.selectedBase && "rag_engine" in knowledge.selectedBase ? knowledge.selectedBase : null
            }
            testing={knowledge.testing}
          />
        )}
      </div>
      {createDrawerOpen && (
        <KnowledgeBaseCreateDrawer
          actionError={knowledge.actionError}
          actionMessage={knowledge.actionMessage}
          canWrite={knowledge.canWriteKnowledge}
          departmentOptions={knowledge.departmentOptions}
          form={knowledge.form}
          onClose={() => setCreateDrawerOpen(false)}
          onCreateKnowledgeBase={createKnowledgeBaseAndClose}
          saving={knowledge.saving}
          setForm={knowledge.setForm}
        />
      )}
    </section>
  );
}
