import { BookOpen, CheckCircle2, ClipboardList, Files, FileText, Route, UploadCloud } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { PageTabs } from "../../components/app-ui";
import { useWorkbenchKnowledgeDocuments } from "../../hooks/useAdminData";
import { useLocale } from "../../i18n-context";
import type {
  ChatMessageResponse,
  WorkbenchAgentInstanceResponse,
  WorkbenchAgentKnowledgeBaseSummary,
  WorkbenchKnowledgeBaseResponse,
} from "../../lib/api";
import { formatCurrency } from "../../lib/formatters";
import { chatConfidenceLabelKey, latestAssistantRunDetails } from "../chat/chatRunDetails";
import { workflowInputKeys, workflowOutputKeys, workflowStepKeys } from "./agentCategory";

type EmployeeGuideTab = "flow" | "inputs" | "outputs";
type EmployeeEvidenceTab = "runtime" | "knowledge" | "governance";

export function AgentGuidePanel({ employee }: { employee: WorkbenchAgentInstanceResponse | null }) {
  const { t } = useLocale();
  const [activeTab, setActiveTab] = useState<EmployeeGuideTab>("flow");
  return (
    <>
      <div className="agent-context-tabs">
        <PageTabs
          active={activeTab}
          onChange={setActiveTab}
          tabs={[
            { id: "flow", label: t("agentWorkbenchGuideFlowTab") },
            { id: "inputs", label: t("agentWorkbenchGuideInputsTab") },
            { id: "outputs", label: t("agentWorkbenchGuideOutputsTab") },
          ]}
        />
      </div>
      {activeTab === "flow" && (
        <section>
          <div className="agent-context-title">
            <ClipboardList size={17} />
            <span>{t("agentWorkbenchFlow")}</span>
          </div>
          <ol className="agent-step-list">
            {workflowStepKeys(employee).map((stepKey, index) => (
              <li key={stepKey}>
                <span>{index + 1}</span>
                {t(stepKey)}
              </li>
            ))}
          </ol>
        </section>
      )}
      {activeTab === "inputs" && (
        <section>
          <div className="agent-context-title">
            <UploadCloud size={17} />
            <span>{t("agentWorkbenchInputs")}</span>
          </div>
          <div className="agent-hint-list">
            {workflowInputKeys(employee).map((inputKey) => (
              <span key={inputKey}>{t(inputKey)}</span>
            ))}
          </div>
        </section>
      )}
      {activeTab === "outputs" && (
        <section>
          <div className="agent-context-title">
            <FileText size={17} />
            <span>{t("agentWorkbenchOutputs")}</span>
          </div>
          <div className="agent-hint-list">
            {workflowOutputKeys(employee).map((outputKey) => (
              <span key={outputKey}>{t(outputKey)}</span>
            ))}
          </div>
        </section>
      )}
      <div className="agent-confidence-note">
        <CheckCircle2 size={16} />
        <span>{t("agentWorkbenchGuardrail")}</span>
      </div>
    </>
  );
}

export function AgentEvidencePanel({ message }: { message: ChatMessageResponse | undefined }) {
  const { t } = useLocale();
  const details = useMemo(() => latestAssistantRunDetails(message ? [message] : []), [message]);
  const [activeTab, setActiveTab] = useState<EmployeeEvidenceTab>("runtime");
  if (!details.message) {
    return (
      <section className="agent-evidence-empty">
        <div className="agent-context-title">
          <Route size={17} />
          <span>{t("agentWorkbenchEvidenceTab")}</span>
        </div>
        <p>{t("agentWorkbenchEvidenceEmpty")}</p>
      </section>
    );
  }
  const guardrail = details.knowledgeRequiresReview ? t("chatRunHumanReviewRequired") : t("chatRunKnowledgeEnabled");
  return (
    <>
      <div className="agent-context-tabs">
        <PageTabs
          active={activeTab}
          onChange={setActiveTab}
          tabs={[
            { id: "runtime", label: t("agentWorkbenchEvidenceRuntimeTab") },
            { id: "knowledge", label: t("agentWorkbenchEvidenceKnowledgeTab") },
            { id: "governance", label: t("agentWorkbenchEvidenceGovernanceTab") },
          ]}
        />
      </div>
      <section className="employee-run-trace" aria-label={t("chatRunDetails")}>
        {activeTab === "runtime" && (
          <>
            <div>
              <span>{t("chatRunModel")}</span>
              <strong>{details.modelKey}</strong>
              <small>{details.providerKey}</small>
            </div>
            <div>
              <span>{t("chatRunRequest")}</span>
              <strong>{details.runtimeTotalTokens}</strong>
              <small>{details.requestId}</small>
            </div>
            <div>
              <span>{t("chatRunRuntimeCost")}</span>
              <strong>{formatCurrency(details.runtimeCostUsd)}</strong>
              <small>{details.runtimeGatewayCalled ? t("chatRunGatewayCalled") : t("chatRunGatewaySkipped")}</small>
            </div>
            <div>
              <span>{t("chatRunRouteAttempts")}</span>
              <strong>{details.runtimeRouteAttempts}</strong>
              <small>
                {t("chatRunFallbackDetail")
                  .replace("{{count}}", details.runtimeFallbackAttempts)
                  .replace("{{mock}}", details.runtimeMockAdapter ? t("commonYes") : t("commonNo"))}
              </small>
            </div>
          </>
        )}
        {activeTab === "knowledge" && (
          <>
            <div>
              <span>{t("chatRunKnowledge")}</span>
              <strong>{t(chatConfidenceLabelKey(details.knowledgeConfidence))}</strong>
              <small>
                {t("chatRunSourcesCount").replace("{{count}}", details.knowledgeSourceCount)} ·{" "}
                {t("chatRunMaxScore").replace("{{score}}", details.knowledgeMaxScore)}
              </small>
            </div>
            <div>
              <span>{t("chatRunKnowledgePlan")}</span>
              <strong>{guardrail}</strong>
              <small>{details.knowledgeReviewReason}</small>
            </div>
          </>
        )}
        {activeTab === "governance" && (
          <>
            <div>
              <span>{t("chatRunLicenseEvidence")}</span>
              <strong>{details.licenseGate}</strong>
              <small>{details.licenseReason}</small>
            </div>
            <div>
              <span>{t("chatRunBudgetEvidence")}</span>
              <strong>{details.budgetGuardStatus}</strong>
              <small>{details.budgetPolicyName}</small>
            </div>
          </>
        )}
      </section>
    </>
  );
}

export function AgentKnowledgePanel({
  bases,
  employee,
  error,
  isPrototype = false,
  loading,
}: {
  bases: WorkbenchKnowledgeBaseResponse[];
  employee: WorkbenchAgentInstanceResponse | null;
  error: string | null;
  isPrototype?: boolean;
  loading: boolean;
}) {
  const { locale, t } = useLocale();
  const [selectedBaseId, setSelectedBaseId] = useState("");
  const activeBases = useMemo(() => bases.filter((base) => base.status === "active"), [bases]);
  const boundBases = employee?.knowledge_bases ?? [];
  const displayBases = boundBases.length ? boundBases : activeBases;
  const selectedBase = displayBases.find((base) => base.id === selectedBaseId) ?? displayBases[0] ?? null;
  const documents = useWorkbenchKnowledgeDocuments(selectedBase?.id ?? null, {
    enabled: Boolean(selectedBase),
    fallbackOnError: isPrototype,
  });

  useEffect(() => {
    if (!selectedBase && selectedBaseId) {
      setSelectedBaseId("");
      return;
    }
    if (selectedBase && selectedBase.id !== selectedBaseId) {
      setSelectedBaseId(selectedBase.id);
    }
  }, [selectedBase, selectedBaseId]);

  if (loading && !boundBases.length) {
    return (
      <section className="employee-knowledge-empty">
        <div className="agent-context-title">
          <BookOpen size={17} />
          <span>{t("agentWorkbenchKnowledgeTab")}</span>
        </div>
        <p>{t("agentWorkbenchKnowledgeLoading")}</p>
      </section>
    );
  }

  if (error && !boundBases.length) {
    return (
      <section className="employee-knowledge-empty">
        <div className="agent-context-title">
          <BookOpen size={17} />
          <span>{t("agentWorkbenchKnowledgeTab")}</span>
        </div>
        <p>{error}</p>
      </section>
    );
  }

  if (!displayBases.length) {
    return (
      <section className="employee-knowledge-empty">
        <div className="agent-context-title">
          <BookOpen size={17} />
          <span>{t("agentWorkbenchKnowledgeTab")}</span>
        </div>
        <p>{t("agentWorkbenchKnowledgeEmpty")}</p>
      </section>
    );
  }

  return (
    <section className="employee-knowledge-panel">
      <div className="agent-context-title">
        <BookOpen size={17} />
        <span>{boundBases.length ? t("agentWorkbenchKnowledgeBound") : t("agentWorkbenchKnowledgeVisible")}</span>
      </div>
      {!boundBases.length && employee?.knowledge_base_count ? (
        <p className="employee-knowledge-note">{t("agentWorkbenchKnowledgeBoundUnavailable")}</p>
      ) : null}
      <div className="employee-knowledge-grid">
        <div className="employee-knowledge-list">
          {displayBases.map((base) => (
            <button
              className={base.id === selectedBase?.id ? "selected" : ""}
              key={base.id}
              onClick={() => setSelectedBaseId(base.id)}
              type="button"
            >
              <strong>{base.name}</strong>
              <span>{base.description || t("agentWorkbenchKnowledgeNoDescription")}</span>
              <small>
                {t("agentWorkbenchKnowledgeDocuments").replace("{{count}}", String(base.document_count))} ·{" "}
                {visibilityLabel(base.visibility, t)}
              </small>
            </button>
          ))}
        </div>
        <div className="employee-knowledge-detail">
          {selectedBase && (
            <>
              <div className="employee-knowledge-detail-head">
                <div>
                  <strong>{selectedBase.name}</strong>
                  <span>
                    {t("agentWorkbenchKnowledgeUpdated").replace(
                      "{{time}}",
                      formatKnowledgeDate(selectedBase.updated_at, locale),
                    )}
                  </span>
                </div>
                <Files size={18} />
              </div>
              <div className="agent-hint-list">
                {selectedBase.tags.length ? (
                  selectedBase.tags.map((tag) => <span key={tag}>{tag}</span>)
                ) : (
                  <span>{visibilityLabel(selectedBase.visibility, t)}</span>
                )}
              </div>
              <div className="employee-knowledge-doc-list">
                {documents.loading && <p>{t("agentWorkbenchKnowledgeDocumentsLoading")}</p>}
                {documents.error && <p>{documents.error}</p>}
                {!documents.loading && !documents.error && !documents.data?.length && (
                  <p>{t("agentWorkbenchKnowledgeNoDocuments")}</p>
                )}
                {(documents.data ?? []).map((document) => (
                  <article key={document.id}>
                    <strong>{document.filename}</strong>
                    <span>
                      {document.status} ·{" "}
                      {t("agentWorkbenchKnowledgeChunks").replace("{{count}}", String(document.chunk_count))}
                    </span>
                  </article>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}

function visibilityLabel(
  visibility: WorkbenchKnowledgeBaseResponse["visibility"] | WorkbenchAgentKnowledgeBaseSummary["visibility"],
  t: (key: string) => string,
) {
  if (visibility === "private") {
    return t("agentWorkbenchKnowledgeVisibilityPrivate");
  }
  if (visibility === "department") {
    return t("agentWorkbenchKnowledgeVisibilityDepartment");
  }
  if (visibility === "tenant") {
    return t("agentWorkbenchKnowledgeVisibilityTenant");
  }
  return visibility;
}

function formatKnowledgeDate(value: string, locale: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}
