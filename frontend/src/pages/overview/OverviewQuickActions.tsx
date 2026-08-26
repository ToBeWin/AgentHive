import type { LucideIcon } from "lucide-react";
import { Bot, Brain, Building2, ChevronRight, CircleDollarSign } from "lucide-react";
import type { PageId, WorkspaceId } from "../../data";
import { useLocale } from "../../i18n-context";

type QuickAction = {
  descriptionKey: string;
  icon: LucideIcon;
  page: PageId;
  titleKey: string;
  workspaces: WorkspaceId[];
};

const quickActions: QuickAction[] = [
  {
    descriptionKey: "overviewQuickActionModelsDesc",
    icon: Brain,
    page: "models",
    titleKey: "overviewQuickActionModels",
    workspaces: ["admin"],
  },
  {
    descriptionKey: "overviewQuickActionAgentsDesc",
    icon: Bot,
    page: "agents",
    titleKey: "overviewQuickActionAgents",
    workspaces: ["admin"],
  },
  {
    descriptionKey: "overviewQuickActionBudgetsDesc",
    icon: CircleDollarSign,
    page: "budgets",
    titleKey: "overviewQuickActionBudgets",
    workspaces: ["admin"],
  },
  {
    descriptionKey: "overviewQuickActionDepartmentsDesc",
    icon: Building2,
    page: "departments",
    titleKey: "overviewQuickActionDepartments",
    workspaces: ["admin"],
  },
];

export function OverviewQuickActions({
  activeWorkspace = "admin",
  onNavigate,
}: {
  activeWorkspace?: WorkspaceId;
  onNavigate?: (page: PageId) => void;
}) {
  const { t } = useLocale();
  const visibleActions = quickActions.filter((action) => action.workspaces.includes(activeWorkspace));

  if (visibleActions.length === 0) {
    return null;
  }

  return (
    <section className="overview-quick-actions-block" aria-label={t("overviewQuickActionsTitle")}>
      <header className="overview-quick-actions-heading">
        <h2>{t("overviewQuickActionsTitle")}</h2>
      </header>
      <div className="overview-quick-actions">
        {visibleActions.map((action) => {
          const Icon = action.icon;
          return (
            <button
              className="overview-quick-action-card"
              key={action.page}
              onClick={() => onNavigate?.(action.page)}
              type="button"
            >
              <span className="overview-quick-action-icon">
                <Icon size={18} />
              </span>
              <span className="overview-quick-action-copy">
                <strong>{t(action.titleKey)}</strong>
                <span>{t(action.descriptionKey)}</span>
              </span>
              <ChevronRight className="overview-quick-action-chevron" size={16} />
            </button>
          );
        })}
      </div>
    </section>
  );
}
