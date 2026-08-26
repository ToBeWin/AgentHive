import { Bot, CheckCircle2, Eye, MessageSquare, PauseCircle, Plus, Route, Search, Settings, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Button, EmptyState, StatusBadge } from "../../components/app-ui";
import { SortableTh, type SortDirection, sortItems } from "../../components/SortableTh";
import { DEFAULT_PAGE_SIZE, paginate, TablePagination } from "../../components/TablePagination";
import { useLocale } from "../../i18n-context";
import { agentDisplayDescription, agentDisplayName } from "../../lib/agentDisplay";
import type { AgentInstanceResponse } from "../../lib/api";
import { readinessReasonLabel } from "../../lib/readiness";
import { type AgentKnowledgeBaseOption, knowledgeBaseLabelsForInstance } from "./agentInstanceUtils";

export function AgentInstanceTable({
  instances,
  canWrite,
  knowledgeBases,
  loading,
  onCreate,
  onInspect,
  onRun,
  onSetStatus,
  onChat,
  onConfigure,
  saving,
}: {
  instances: AgentInstanceResponse[];
  canWrite: boolean;
  knowledgeBases: AgentKnowledgeBaseOption[];
  loading: boolean;
  onCreate?: () => void;
  onInspect: (instance: AgentInstanceResponse) => void;
  onRun: (instance: AgentInstanceResponse) => void;
  onSetStatus: (instance: AgentInstanceResponse, status: "active" | "disabled") => void;
  onChat?: (instance: AgentInstanceResponse) => void;
  onConfigure?: (instance: AgentInstanceResponse) => void;
  saving: boolean;
}) {
  const { locale, t } = useLocale();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "disabled">("all");
  const filterKey = `${instances.length}:${query}:${statusFilter}`;
  const [lastFilterKey, setLastFilterKey] = useState(filterKey);
  if (filterKey !== lastFilterKey) {
    setLastFilterKey(filterKey);
    setPage(1);
  }

  const handleSort = (key: string, direction: SortDirection) => {
    setSortKey(key);
    setSortDirection(direction);
    setPage(1);
  };

  const filteredInstances = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return instances.filter((instance) => {
      const knowledgeLabels = knowledgeBaseLabelsForInstance(instance, knowledgeBases);
      const searchable = [
        agentDisplayName(instance, locale),
        agentDisplayDescription(instance, locale),
        instance.agent_key,
        instance.module_key,
        instance.model_key ?? "",
        instance.model_routing_key ?? "",
        instance.visibility,
        ...knowledgeLabels,
      ]
        .join(" ")
        .toLocaleLowerCase();
      return (
        (!normalizedQuery || searchable.includes(normalizedQuery)) &&
        (statusFilter === "all" || instance.status === statusFilter)
      );
    });
  }, [instances, knowledgeBases, locale, query, statusFilter]);

  const sortedInstances =
    sortKey && sortDirection
      ? sortItems(filteredInstances, sortKey, sortDirection, (item, key) => {
          switch (key) {
            case "name":
              return item.name || "";
            case "status":
              return item.status || "";
            case "created_at":
              return new Date(item.created_at || 0);
            case "updated_at":
              return new Date(item.updated_at || 0);
            default:
              return "";
          }
        })
      : filteredInstances;

  const totalPages = Math.max(1, Math.ceil(sortedInstances.length / pageSize));
  const safePage = Math.min(Math.max(1, page), totalPages);
  const pagedInstances = paginate(sortedInstances, { page: safePage, pageSize });

  return (
    <>
      <div className="collection-toolbar agent-table-toolbar">
        <label className="collection-search">
          <Search size={16} aria-hidden="true" />
          <span className="visually-hidden">{t("agentsInstanceSearchLabel")}</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("agentsInstanceSearchPlaceholder")}
            aria-label={t("agentsInstanceSearchLabel")}
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
        <label className="collection-filter">
          <span>{t("agentsInstanceFilterLabel")}</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}>
            <option value="all">{t("agentsInstanceFilterAll")}</option>
            <option value="active">{t("agentsInstanceFilterActive")}</option>
            <option value="disabled">{t("agentsInstanceFilterDisabled")}</option>
          </select>
        </label>
        <span className="collection-toolbar-meta">
          {t("agentsInstanceResults")
            .replace("{{visible}}", String(filteredInstances.length))
            .replace("{{total}}", String(instances.length))}
        </span>
      </div>
      <table className="data-table compact-table agent-instance-table">
        <thead>
          <tr>
            <SortableTh
              label={t("agentsName")}
              sortKey="name"
              currentSortKey={sortKey ?? undefined}
              currentDirection={sortDirection ?? undefined}
              onSort={handleSort}
            />
            <th>{t("agentInstancesBaseAgentColumn")}</th>
            <th>{t("agentInstancesVisibility")}</th>
            <th>{t("agentInstancesRoute")}</th>
            <th>{t("agentInstancesKnowledge")}</th>
            <SortableTh
              label={t("agentsStatus")}
              sortKey="status"
              currentSortKey={sortKey ?? undefined}
              currentDirection={sortDirection ?? undefined}
              onSort={handleSort}
            />
            <th>{t("agentInstancesActions")}</th>
          </tr>
        </thead>
        <tbody>
          {pagedInstances.map((instance) => {
            const knowledgeLabels = knowledgeBaseLabelsForInstance(instance, knowledgeBases);
            return (
              <tr key={instance.id}>
                <td>
                  <span className="avatar">
                    <Bot size={17} />
                  </span>
                  <div>
                    <strong>{agentDisplayName(instance, locale)}</strong>
                    <span className="row-subtitle">{agentDisplayDescription(instance, locale) || instance.slug}</span>
                  </div>
                </td>
                <td>
                  <code>{instance.agent_key}</code>
                  <span className="row-subtitle">{instance.module_key}</span>
                </td>
                <td>{instance.visibility}</td>
                <td>
                  {instance.model_routing_key ?? t("agentsPolicyDefault")}
                  <span className="row-subtitle">{instance.model_key ?? t("agentsModelSelectedByPolicy")}</span>
                </td>
                <td>
                  <KnowledgeBindingSummary labels={knowledgeLabels} />
                </td>
                <td>
                  <StatusBadge status={instance.status} />
                  <ReadinessInline instance={instance} />
                </td>
                <td>
                  <div className="provider-actions">
                    <div className="agent-quick-actions">
                      <button
                        type="button"
                        className="agent-quick-action"
                        onClick={() => onChat?.(instance)}
                        aria-label={t("agentsQuickChat")}
                        title={t("agentsQuickChat")}
                      >
                        <MessageSquare size={15} />
                      </button>
                      <button
                        type="button"
                        className="agent-quick-action"
                        onClick={() => onConfigure?.(instance)}
                        aria-label={t("agentsQuickConfigure")}
                        title={t("agentsQuickConfigure")}
                      >
                        <Settings size={15} />
                      </button>
                    </div>
                    <Button onClick={() => onInspect(instance)}>
                      <Eye size={15} /> {t("agentInstancesDetail")}
                    </Button>
                    <Button onClick={() => onRun(instance)}>
                      <Route size={15} /> {t("agentsTabRuntime")}
                    </Button>
                    <Button
                      onClick={() => onSetStatus(instance, "active")}
                      disabled={!canWrite || saving || instance.status === "active"}
                    >
                      <CheckCircle2 size={15} /> {t("agentInstancesEnable")}
                    </Button>
                    <Button
                      onClick={() => onSetStatus(instance, "disabled")}
                      disabled={!canWrite || saving || instance.status === "disabled"}
                    >
                      <PauseCircle size={15} /> {t("agentInstancesDisable")}
                    </Button>
                  </div>
                </td>
              </tr>
            );
          })}
          {!loading && instances.length === 0 && (
            <tr>
              <td className="table-empty-cell" colSpan={7}>
                <EmptyState
                  icon={<Bot />}
                  title={t("emptyTitleAgents")}
                  message={t("agentInstancesEmpty")}
                  action={
                    onCreate && canWrite ? (
                      <Button variant="primary" onClick={onCreate}>
                        <Plus size={16} /> {t("agentInstancesCreate")}
                      </Button>
                    ) : undefined
                  }
                />
              </td>
            </tr>
          )}
          {!loading && instances.length > 0 && filteredInstances.length === 0 && (
            <tr>
              <td className="table-empty-cell" colSpan={7}>
                <EmptyState
                  icon={<Search />}
                  title={t("agentsInstanceNoMatches")}
                  message={t("agentsInstanceNoMatchesDetail")}
                />
              </td>
            </tr>
          )}
          {loading && (
            <tr>
              <td className="table-empty-cell" colSpan={7}>
                {t("agentInstancesLoading")}
              </td>
            </tr>
          )}
        </tbody>
      </table>
      <TablePagination
        total={filteredInstances.length}
        page={safePage}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(size) => {
          setPageSize(size);
          setPage(1);
        }}
      />
    </>
  );
}

function ReadinessInline({ instance }: { instance: AgentInstanceResponse }) {
  const { t } = useLocale();
  if (instance.runnable !== false) {
    return <span className="row-subtitle">{t("agentInstancesReadyForHandoff")}</span>;
  }
  const labels = (instance.readiness_reasons ?? []).map((reason) => readinessReasonLabel(reason, t));
  return <span className="row-subtitle warning-text">{labels.slice(0, 2).join(" / ")}</span>;
}

function KnowledgeBindingSummary({ labels }: { labels: string[] }) {
  const { t } = useLocale();
  if (!labels.length) {
    return <span className="row-subtitle">{t("agentsNoKnowledgeBase")}</span>;
  }
  return (
    <div className="agent-knowledge-bindings">
      <strong>{t("agentsSourcesCount").replace("{{count}}", String(labels.length))}</strong>
      <span className="row-subtitle">{labels.slice(0, 2).join(" / ")}</span>
      {labels.length > 2 && <span className="row-subtitle">+{labels.length - 2}</span>}
    </div>
  );
}
