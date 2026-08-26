import { Bot, CheckCircle2, Database, FileSearch, type LucideIcon, UploadCloud } from "lucide-react";
import { useState } from "react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { RetrievalTestResponse } from "../../lib/api";
import type { KnowledgeBaseListItem, KnowledgeDocumentListItem } from "./useKnowledgePageController";

type KnowledgeDocumentsTab = "readiness" | "documents" | "binding";
type KnowledgeLoopStageId = "base" | "documents" | "retrieval" | "binding";

interface KnowledgeHandoffLoopPanelProps {
  activeTab: KnowledgeDocumentsTab;
  documentList: KnowledgeDocumentListItem[];
  onOpenAgentBinding: () => void;
  onOpenRetrieval: () => void;
  onPickUploadFile: () => void;
  onSelectTab: (tab: KnowledgeDocumentsTab) => void;
  retrievalResult: RetrievalTestResponse | null;
  selectedBase: KnowledgeBaseListItem | null;
}

export function KnowledgeHandoffLoopPanel({
  activeTab,
  documentList,
  onOpenAgentBinding,
  onOpenRetrieval,
  onPickUploadFile,
  onSelectTab,
  retrievalResult,
  selectedBase,
}: KnowledgeHandoffLoopPanelProps) {
  const { t } = useLocale();
  const indexedCount = documentList.filter((document) => document.status === "indexed").length;
  const failedCount = documentList.filter((document) => document.status === "failed").length;
  const processingCount = documentList.filter((document) =>
    ["pending_upload", "uploaded", "ingesting"].includes(document.status),
  ).length;
  const verifiedRetrieval =
    Boolean(selectedBase) &&
    retrievalResult?.knowledge_base_id === selectedBase?.id &&
    (retrievalResult?.results.length ?? 0) > 0;
  const stages: Array<{
    action: () => void;
    detail: string;
    icon: LucideIcon;
    id: KnowledgeLoopStageId;
    metric: string;
    status: string;
    title: string;
    tone: "ok" | "warning" | "blocked";
  }> = [
    {
      action: () => onSelectTab("readiness"),
      detail: selectedBase
        ? t("knowledgeLoopBaseDetail").replace("{{visibility}}", selectedBase.visibility)
        : t("knowledgeLoopBaseMissingDetail"),
      icon: Database,
      id: "base",
      metric: selectedBase ? selectedBase.name : t("knowledgeLoopNoBase"),
      status: selectedBase ? t("knowledgeLoopReady") : t("knowledgeLoopNeedsBase"),
      title: t("knowledgeLoopBase"),
      tone: selectedBase ? "ok" : "blocked",
    },
    {
      action: () => (selectedBase ? onPickUploadFile() : onSelectTab("documents")),
      detail: t("knowledgeLoopDocumentsDetail")
        .replace("{{processing}}", String(processingCount))
        .replace("{{failed}}", String(failedCount)),
      icon: UploadCloud,
      id: "documents",
      metric: t("knowledgeLoopDocumentsMetric")
        .replace("{{indexed}}", String(indexedCount))
        .replace("{{total}}", String(documentList.length)),
      status: indexedCount ? t("knowledgeLoopReady") : t("knowledgeLoopNeedsDocuments"),
      title: t("knowledgeLoopDocuments"),
      tone: indexedCount && !failedCount ? "ok" : documentList.length ? "warning" : "blocked",
    },
    {
      action: onOpenRetrieval,
      detail: t("knowledgeLoopRetrievalDetail").replace("{{count}}", String(retrievalResult?.results.length ?? 0)),
      icon: FileSearch,
      id: "retrieval",
      metric: verifiedRetrieval ? t("knowledgeLoopRetrievalVerified") : t("knowledgeLoopRetrievalUnverified"),
      status: verifiedRetrieval ? t("knowledgeLoopReady") : t("knowledgeLoopNeedsRetrieval"),
      title: t("knowledgeLoopRetrieval"),
      tone: verifiedRetrieval ? "ok" : indexedCount ? "warning" : "blocked",
    },
    {
      action: onOpenAgentBinding,
      detail: t("knowledgeLoopBindingDetail"),
      icon: Bot,
      id: "binding",
      metric: t("knowledgeLoopBindingMetric"),
      status: indexedCount && verifiedRetrieval ? t("knowledgeLoopReady") : t("knowledgeLoopNeedsBinding"),
      title: t("knowledgeLoopBinding"),
      tone: indexedCount && verifiedRetrieval ? "ok" : indexedCount ? "warning" : "blocked",
    },
  ];
  const preferredStageId =
    stages.find((stage) => stage.tone === "blocked")?.id ??
    stages.find((stage) => stage.tone === "warning")?.id ??
    activeStageId(activeTab);
  const [selectedStageId, setSelectedStageId] = useState<KnowledgeLoopStageId>(() => preferredStageId);
  const selectedStage = stages.find((stage) => stage.id === selectedStageId) ?? stages[0];
  const SelectedIcon = selectedStage.icon;
  const readyCount = stages.filter((stage) => stage.tone === "ok").length;
  const reviewCount = stages.filter((stage) => stage.tone === "warning").length;
  const blockedCount = stages.filter((stage) => stage.tone === "blocked").length;

  return (
    <details className="knowledge-handoff-loop" aria-label={t("knowledgeLoopTitle")}>
      <summary className="knowledge-handoff-loop-summary">
        <div>
          <span>{t("knowledgeLoopEyebrow")}</span>
          <strong>{t("knowledgeLoopTitle")}</strong>
          <small>{t("knowledgeLoopCollapseHint")}</small>
        </div>
        <div className="knowledge-handoff-loop-summary-status">
          <StatusBadge status={t("knowledgeLoopReadyCount").replace("{{count}}", String(readyCount))} />
          {reviewCount > 0 && (
            <StatusBadge status={t("knowledgeLoopReviewCount").replace("{{count}}", String(reviewCount))} />
          )}
          {blockedCount > 0 && (
            <StatusBadge status={t("knowledgeLoopBlockedCount").replace("{{count}}", String(blockedCount))} />
          )}
        </div>
      </summary>
      <p className="knowledge-handoff-loop-description">{t("knowledgeLoopDescription")}</p>
      <div className="knowledge-handoff-loop-workspace">
        <div className="knowledge-handoff-loop-steps" role="tablist" aria-label={t("knowledgeLoopStageTabs")}>
          {stages.map((stage) => {
            const Icon = stage.icon;
            return (
              <button
                aria-selected={stage.id === selectedStage.id}
                className={cx(
                  "knowledge-handoff-loop-step",
                  stage.tone,
                  stage.id === activeStageId(activeTab) && "active-workspace",
                  stage.id === selectedStage.id && "selected",
                )}
                disabled={stage.id !== "base" && !selectedBase}
                key={stage.id}
                onClick={() => setSelectedStageId(stage.id)}
                role="tab"
                type="button"
              >
                <span className="knowledge-handoff-loop-index">
                  <Icon size={16} />
                </span>
                <span>
                  <strong>{stage.title}</strong>
                  <small>{stage.status}</small>
                </span>
              </button>
            );
          })}
        </div>
        <div className={cx("knowledge-handoff-loop-detail", selectedStage.tone)} role="tabpanel">
          <div className="knowledge-handoff-loop-detail-head">
            <span className="knowledge-handoff-loop-icon">
              <SelectedIcon size={18} />
            </span>
            <div>
              <span>{t("knowledgeLoopSelectedStage")}</span>
              <strong>{selectedStage.title}</strong>
              <small>{selectedStage.detail}</small>
            </div>
            <StatusBadge status={selectedStage.status} />
          </div>
          <div className="knowledge-handoff-loop-detail-metric">
            <span>{t("knowledgeLoopCurrentMetric")}</span>
            <strong>{selectedStage.metric}</strong>
          </div>
          <button
            className="button"
            disabled={selectedStage.id !== "base" && !selectedBase}
            onClick={selectedStage.action}
            type="button"
          >
            {t("knowledgeLoopOpenStep")}
          </button>
        </div>
      </div>
      {indexedCount > 0 && verifiedRetrieval && (
        <div className="knowledge-handoff-loop-note">
          <CheckCircle2 size={15} />
          <span>{t("knowledgeLoopReadyHint")}</span>
        </div>
      )}
    </details>
  );
}

function activeStageId(activeTab: KnowledgeDocumentsTab): KnowledgeLoopStageId {
  if (activeTab === "documents") {
    return "documents";
  }
  if (activeTab === "binding") {
    return "binding";
  }
  return "base";
}
