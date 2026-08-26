import { Database, Plus, Search, Trash2, X } from "lucide-react";
import { useMemo, useState } from "react";
import { ApiNotice, Button, ConfirmDialog, cx, EmptyState } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type {
  KnowledgeBaseResponse,
  KnowledgeBaseVisibility,
  RAGEngineType,
  WorkbenchKnowledgeBaseResponse,
} from "../../lib/api";
import { formatKnowledgeVisibilityLabel } from "./knowledgeUtils";

type KnowledgeBaseListItem = KnowledgeBaseResponse | WorkbenchKnowledgeBaseResponse;

interface KnowledgeBaseFormState {
  departmentIds: string[];
  description: string;
  name: string;
  ragEngine: RAGEngineType;
  tags: string;
  visibility: KnowledgeBaseVisibility;
}

interface KnowledgeBaseSidebarProps {
  baseList: KnowledgeBaseListItem[];
  basesError: string | null;
  basesLoading: boolean;
  canWrite: boolean;
  countLabelKey?: string;
  deletingBaseId: string | null;
  onCreateClick: () => void;
  onDeleteKnowledgeBase: (id: string) => void;
  onSelectBase: (id: string) => void;
  refetchBases: () => void;
  selectedBaseId: string | null;
  titleKey?: string;
}

export function KnowledgeBaseSidebar({
  baseList,
  basesError,
  basesLoading,
  canWrite,
  countLabelKey = "knowledgeSidebarBases",
  deletingBaseId,
  onCreateClick,
  onDeleteKnowledgeBase,
  onSelectBase,
  refetchBases,
  selectedBaseId,
  titleKey = "knowledgeBasesTitle",
}: KnowledgeBaseSidebarProps) {
  const { t } = useLocale();
  const [pendingDeleteBase, setPendingDeleteBase] = useState<KnowledgeBaseListItem | null>(null);
  const [query, setQuery] = useState("");

  const filteredBaseList = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    if (!normalizedQuery) {
      return baseList;
    }
    return baseList.filter((base) =>
      [base.name, base.description ?? "", "rag_engine" in base ? base.rag_engine : ""]
        .join(" ")
        .toLocaleLowerCase()
        .includes(normalizedQuery),
    );
  }, [baseList, query]);

  const confirmDeleteBase = () => {
    const target = pendingDeleteBase;
    setPendingDeleteBase(null);
    if (target) {
      onDeleteKnowledgeBase(target.id);
    }
  };

  return (
    <aside className="kb-list">
      <div className="list-title">
        <h2>{t(titleKey)}</h2>
        {canWrite && (
          <Button variant="ghost" onClick={onCreateClick}>
            <Plus size={16} /> {t("knowledgeNewBase")}
          </Button>
        )}
      </div>
      <div className="kb-sidebar-count">
        {t(countLabelKey)} · {baseList.length}
      </div>
      <label className="collection-search kb-sidebar-search">
        <Search size={16} aria-hidden="true" />
        <span className="visually-hidden">{t("knowledgeSearchBasesLabel")}</span>
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t("knowledgeSearchBasesPlaceholder")}
          aria-label={t("knowledgeSearchBasesLabel")}
        />
        {query && (
          <button
            className="collection-search-clear"
            type="button"
            onClick={() => setQuery("")}
            aria-label={t("commonClearSearch")}
            title={t("commonClearSearch")}
          >
            <X size={14} aria-hidden="true" />
          </button>
        )}
      </label>
      <div className="kb-sidebar-panel">
        {basesLoading && <div className="budget-empty-state">{t("knowledgeLoadingBases")}</div>}
        {basesError && !basesLoading && (
          <ApiNotice
            title={t("knowledgeApiUnavailable")}
            message={basesError}
            action={<Button onClick={refetchBases}>{t("commonRetry")}</Button>}
          />
        )}
        {!basesLoading && !basesError && !baseList.length && (
          <EmptyState
            icon={<Database />}
            title={t("emptyTitleKnowledge")}
            message={canWrite ? t("knowledgeEmptyBases") : t("knowledgeEmptyVisibleBases")}
            action={
              canWrite ? (
                <Button variant="primary" onClick={onCreateClick}>
                  <Plus size={16} /> {t("knowledgeNewBase")}
                </Button>
              ) : undefined
            }
          />
        )}
        {!basesLoading && !basesError && baseList.length > 0 && !filteredBaseList.length && (
          <EmptyState
            icon={<Search />}
            title={t("knowledgeNoBaseMatches")}
            message={t("knowledgeNoBaseMatchesDetail")}
          />
        )}
        {filteredBaseList.map((base) => (
          <div className={cx("kb-card", selectedBaseId === base.id && "selected")} key={base.id}>
            <button className="kb-card-main" onClick={() => onSelectBase(base.id)} type="button">
              <div>
                <strong>{base.name}</strong>
              </div>
              <p>
                {t("knowledgeDocsCount").replace("{{count}}", String(base.document_count))} ·{" "}
                {formatKnowledgeVisibilityLabel(base.visibility, t)}
                {base.visibility === "department"
                  ? ` (${t("knowledgeDepartmentsCount").replace("{{count}}", String(base.department_ids.length))})`
                  : ""}
                {"rag_engine" in base ? ` · ${base.rag_engine}` : ""}
              </p>
              {base.description && <span>{base.description}</span>}
            </button>
            {canWrite && (
              <button
                aria-label={t("knowledgeDeleteBase")}
                className="kb-card-action"
                disabled={deletingBaseId === base.id}
                onClick={() => setPendingDeleteBase(base)}
                type="button"
              >
                <Trash2 size={16} />
              </button>
            )}
          </div>
        ))}
      </div>
      <ConfirmDialog
        open={Boolean(pendingDeleteBase)}
        title={t("knowledgeDeleteBase")}
        message={pendingDeleteBase ? t("knowledgeDeleteBaseConfirm").replace("{{name}}", pendingDeleteBase.name) : ""}
        confirmLabel={t("knowledgeDeleteBase")}
        cancelLabel={t("commonClose")}
        variant="danger"
        onConfirm={confirmDeleteBase}
        onCancel={() => setPendingDeleteBase(null)}
      />
    </aside>
  );
}

export type { KnowledgeBaseFormState };
