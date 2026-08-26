import { Bot } from "lucide-react";
import type { NavItem, PageId, WorkspaceId } from "../../data";
import { type Locale, t } from "../../i18n";
import { agentDisplayName } from "../../lib/agentDisplay";
import type { WorkbenchAgentInstanceResponse } from "../../lib/api";
import { workspacePageLabelKey } from "../../lib/workspaces";
import { cx } from "../app-ui";

interface WorkspaceNavigationProps {
  active: PageId;
  activeAgents: WorkbenchAgentInstanceResponse[];
  activeWorkspace: WorkspaceId;
  locale: Locale;
  mainNav: NavItem[];
  onNavigate: (pageId: PageId) => void;
  onNavigateAgent: (agentId: string) => void;
  preloadPage?: (id: PageId) => void;
  selectedAgentId: string | null;
  settings?: NavItem;
  workbenchNav?: NavItem;
}

interface NavigationGroup {
  titleKey: string;
  pageIds: PageId[];
}

export function WorkspaceNavigation({
  active,
  activeAgents,
  activeWorkspace,
  locale,
  mainNav,
  onNavigate,
  onNavigateAgent,
  preloadPage,
  selectedAgentId,
  settings,
  workbenchNav,
}: WorkspaceNavigationProps) {
  const SettingsIcon = settings?.icon;
  const groupedNav = groupNavigation(activeWorkspace, mainNav);

  return (
    <>
      <nav className="nav-list">
        {workbenchNav && (
          <NavButton
            active={active === workbenchNav.id}
            activeWorkspace={activeWorkspace}
            item={workbenchNav}
            locale={locale}
            onNavigate={onNavigate}
            preloadPage={preloadPage}
          />
        )}
        {activeWorkspace === "user" && activeAgents.length > 0 && (
          <fieldset className="agent-nav-section">
            <legend className="nav-section-title">{t(locale, "agentMenuLabel")}</legend>
            {activeAgents.map((agent) => (
              <button
                key={agent.id}
                type="button"
                className={cx(
                  "agent-nav-item",
                  active === "digitalEmployees" && selectedAgentId === agent.id && "active",
                )}
                onClick={() => onNavigateAgent(agent.id)}
                title={agentDisplayName(agent, locale)}
              >
                <Bot size={17} strokeWidth={1.8} aria-hidden="true" />
                <span>{agentDisplayName(agent, locale)}</span>
              </button>
            ))}
          </fieldset>
        )}
        {groupedNav.map((group) => (
          <section className="nav-group" key={group.titleKey}>
            <span className="nav-section-title">{t(locale, group.titleKey)}</span>
            <div className="nav-group-list">
              {group.items.map((item) => (
                <NavButton
                  active={active === item.id}
                  activeWorkspace={activeWorkspace}
                  item={item}
                  key={item.id}
                  locale={locale}
                  onNavigate={onNavigate}
                  preloadPage={preloadPage}
                />
              ))}
            </div>
          </section>
        ))}
      </nav>
      {settings && SettingsIcon && (
        <div className="nav-footer">
          <span className="nav-section-title">{t(locale, "navSectionSystem")}</span>
          <NavButton
            active={active === settings.id}
            activeWorkspace={activeWorkspace}
            item={settings}
            locale={locale}
            onNavigate={onNavigate}
            preloadPage={preloadPage}
          />
        </div>
      )}
    </>
  );
}

function NavButton({
  active,
  activeWorkspace,
  item,
  locale,
  onNavigate,
  preloadPage,
}: {
  active: boolean;
  activeWorkspace: WorkspaceId;
  item: NavItem;
  locale: Locale;
  onNavigate: (pageId: PageId) => void;
  preloadPage?: (id: PageId) => void;
}) {
  const Icon = item.icon;
  const label = t(locale, workspacePageLabelKey(item.id, activeWorkspace));
  return (
    <button
      type="button"
      className={cx("nav-item", active && "active")}
      onFocus={() => preloadPage?.(item.id)}
      onMouseEnter={() => preloadPage?.(item.id)}
      onClick={() => onNavigate(item.id)}
      title={label}
    >
      <Icon size={20} strokeWidth={1.7} aria-hidden="true" />
      <span>{label}</span>
    </button>
  );
}

function groupNavigation(activeWorkspace: WorkspaceId, items: NavItem[]) {
  const definitions = navigationGroupsByWorkspace[activeWorkspace];
  const grouped = definitions
    .map((definition) => ({
      titleKey: definition.titleKey,
      items: definition.pageIds.map((pageId) => items.find((item) => item.id === pageId)).filter(Boolean) as NavItem[],
    }))
    .filter((group) => group.items.length > 0);
  const assigned = new Set(definitions.flatMap((definition) => definition.pageIds));
  const unassigned = items.filter((item) => !assigned.has(item.id));

  if (unassigned.length) {
    grouped.push({ titleKey: "navGroupOther", items: unassigned });
  }

  return grouped;
}

const navigationGroupsByWorkspace: Record<WorkspaceId, NavigationGroup[]> = {
  user: [
    {
      titleKey: "navGroupUserTools",
      pageIds: ["mediaGeneration", "knowledgeBases"],
    },
  ],
  admin: [
    {
      titleKey: "navGroupOperate",
      pageIds: ["overview"],
    },
    {
      titleKey: "navGroupAgentDelivery",
      pageIds: ["agents", "knowledgeBases", "channels"],
    },
    {
      titleKey: "navGroupModelGovernance",
      pageIds: ["models", "budgets"],
    },
    {
      titleKey: "navGroupOrgFinance",
      pageIds: ["users", "departments"],
    },
  ],
};
