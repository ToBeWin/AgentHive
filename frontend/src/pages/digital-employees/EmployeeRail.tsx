import {
  BarChart3,
  Bot,
  ChevronDown,
  ChevronUp,
  Landmark,
  Megaphone,
  ShoppingBag,
  Sparkles,
  UserRoundCheck,
  UsersRound,
} from "lucide-react";
import { useState } from "react";
import { ApiNotice, cx } from "../../components/app-ui";
import type { Locale } from "../../i18n";
import { useLocale } from "../../i18n-context";
import { agentDisplayDescription, agentDisplayName, localizedTaskTitle } from "../../lib/agentDisplay";
import type { ChatSessionResponse, WorkbenchAgentInstanceResponse } from "../../lib/api";
import { categoryForEmployee, categoryLabelKey, categoryOrder, type EmployeeCategory } from "./agentCategory";

export function EmployeeRail({
  activeCategory,
  activeEmployeesCount,
  categoryCounts,
  loading,
  onActiveCategoryChange,
  onSelectEmployee,
  onSelectSession,
  selectedSessionId,
  selectedEmployee,
  selectedEmployeeSessions,
  visibleEmployees,
}: {
  activeCategory: EmployeeCategory;
  activeEmployeesCount: number;
  categoryCounts: Record<EmployeeCategory, number>;
  loading: boolean;
  onActiveCategoryChange: (category: EmployeeCategory) => void;
  onSelectEmployee: (employee: WorkbenchAgentInstanceResponse) => void;
  onSelectSession: (session: ChatSessionResponse) => void;
  selectedSessionId: string | null;
  selectedEmployee: WorkbenchAgentInstanceResponse | null;
  selectedEmployeeSessions: ChatSessionResponse[];
  visibleEmployees: WorkbenchAgentInstanceResponse[];
}) {
  const { locale, t } = useLocale();
  const [recentOpen, setRecentOpen] = useState(false);
  const visibleCategories = categoryOrder.filter((category) => category === "all" || categoryCounts[category] > 0);
  const showCategoryBar = visibleCategories.length > 2;

  return (
    <aside className="employee-rail">
      <div className="employee-rail-head">
        <span>{t("digitalEmployeesMyAgents")}</span>
        <strong>{activeEmployeesCount}</strong>
      </div>

      {showCategoryBar && (
        <div className="employee-category-list">
          {visibleCategories.map((category) => (
            <button
              className={cx("employee-category", activeCategory === category && "active")}
              key={category}
              onClick={() => onActiveCategoryChange(category)}
              aria-pressed={activeCategory === category}
              type="button"
            >
              <span>{t(categoryLabelKey(category))}</span>
              <strong>{categoryCounts[category]}</strong>
            </button>
          ))}
        </div>
      )}

      <div className="employee-list">
        {visibleEmployees.map((employee) => {
          const Icon = employeeIcon(employee);
          return (
            <button
              className={cx("employee-card", selectedEmployee?.id === employee.id && "selected")}
              key={employee.id}
              onClick={() => onSelectEmployee(employee)}
              type="button"
            >
              <span className="employee-avatar">
                <Icon size={22} />
              </span>
              <span>
                <strong>{agentDisplayName(employee, locale)}</strong>
                <small>{agentDisplayDescription(employee, locale) || t("digitalEmployeesReady")}</small>
              </span>
            </button>
          );
        })}
        {!visibleEmployees.length && !loading && (
          <ApiNotice title={t("digitalEmployeesEmptyTitle")} message={t("digitalEmployeesEmptyMessage")} />
        )}
      </div>

      <div className="employee-recent">
        <button
          type="button"
          className="employee-recent-toggle"
          aria-expanded={recentOpen}
          onClick={() => setRecentOpen((open) => !open)}
        >
          <span>{t("digitalEmployeesRecentChats")}</span>
          {recentOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
        {recentOpen && (
          <>
            {selectedEmployeeSessions.slice(0, 8).map((session) => (
              <button
                className={cx("employee-task-link", selectedSessionId === session.id && "selected")}
                key={session.id}
                type="button"
                onClick={() => onSelectSession(session)}
              >
                <strong>{sessionTaskTitle(session, locale)}</strong>
                <span className="employee-task-link-meta">
                  <small>{sessionTaskUpdatedAt(session, locale)}</small>
                </span>
              </button>
            ))}
            {selectedEmployee ? (
              selectedEmployeeSessions.length === 0 && <small>{t("digitalEmployeesNoRecentChats")}</small>
            ) : (
              <small>{t("digitalEmployeesSelectOneDetail")}</small>
            )}
          </>
        )}
      </div>
    </aside>
  );
}

function employeeIcon(employee: WorkbenchAgentInstanceResponse) {
  const category = categoryForEmployee(employee);
  if (category === "customer") {
    return UserRoundCheck;
  }
  if (category === "marketing") {
    return Megaphone;
  }
  if (category === "hr") {
    return UsersRound;
  }
  if (category === "media") {
    return Sparkles;
  }
  if (category === "operations") {
    return ShoppingBag;
  }
  if (category === "finance") {
    return Landmark;
  }
  if (category === "analytics") {
    return BarChart3;
  }
  return Bot;
}

function sessionTaskTitle(session: ChatSessionResponse, locale: Locale) {
  const lastTask = session.metadata.last_task;
  if (isRecord(lastTask) && typeof lastTask.title === "string" && lastTask.title.trim()) {
    return localizedTaskTitle(lastTask.title, locale);
  }
  return localizedTaskTitle(session.title, locale);
}

function sessionTaskUpdatedAt(session: ChatSessionResponse, locale: Locale) {
  const lastTask = session.metadata.last_task;
  const rawUpdatedAt =
    isRecord(lastTask) && typeof lastTask.completed_at === "string" ? lastTask.completed_at : session.updated_at;
  const date = new Date(rawUpdatedAt);
  if (Number.isNaN(date.getTime())) {
    return rawUpdatedAt;
  }
  return new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "2-digit",
  }).format(date);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
