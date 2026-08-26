import { ChevronDown, ChevronUp } from "lucide-react";
import { useEffect, useState } from "react";
import type { NavItem, PageId, WorkspaceId } from "../../data";
import { type Locale, t } from "../../i18n";
import { workspacePageLabelKey } from "../../lib/workspaces";
import { cx } from "../app-ui";

interface WorkspaceCommandCenterProps {
  active: PageId;
  activeWorkspace: WorkspaceId;
  locale: Locale;
  onNavigate: (pageId: PageId) => void;
  preloadPage?: (pageId: PageId) => void;
  visibleNav: NavItem[];
}

interface WorkspaceCommandDefinition {
  descriptionKey: string;
  pageId: PageId;
  titleKey?: string;
}

export function WorkspaceCommandCenter({
  active,
  activeWorkspace,
  locale,
  onNavigate,
  preloadPage,
  visibleNav,
}: WorkspaceCommandCenterProps) {
  const [collapsed, setCollapsed] = useState(() => storedCommandCenterCollapsed(activeWorkspace));
  const visiblePageIds = new Set(visibleNav.map((item) => item.id));
  const commands = commandDefinitionsByWorkspace[activeWorkspace]
    .filter((command) => visiblePageIds.has(command.pageId))
    .map((command) => {
      const item = visibleNav.find((navItem) => navItem.id === command.pageId);
      return item ? { ...command, item } : null;
    })
    .filter(Boolean) as Array<WorkspaceCommandDefinition & { item: NavItem }>;

  useEffect(() => {
    setCollapsed(storedCommandCenterCollapsed(activeWorkspace));
  }, [activeWorkspace]);

  if (commands.length === 0) {
    return null;
  }

  const toggleCollapsed = () => {
    setCollapsed((value) => {
      const next = !value;
      saveCommandCenterCollapsed(activeWorkspace, next);
      return next;
    });
  };

  return (
    <section
      className={cx("workspace-command-center", collapsed && "collapsed")}
      aria-label={t(locale, "workspaceCommandCenter")}
    >
      <div className="workspace-command-copy">
        <strong>{t(locale, workspaceCommandTitleKey(activeWorkspace))}</strong>
        {!collapsed && (
          <>
            <span>{t(locale, workspaceCommandEyebrowKey(activeWorkspace))}</span>
            <small>{t(locale, "workspaceCommandShortcutsCount").replace("{{count}}", String(commands.length))}</small>
          </>
        )}
      </div>
      <button type="button" className="workspace-command-toggle" aria-expanded={!collapsed} onClick={toggleCollapsed}>
        {collapsed ? t(locale, "workspaceCommandExpand") : t(locale, "workspaceCommandCollapse")}
        {collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
      </button>
      {!collapsed && (
        <div className="workspace-command-list">
          {commands.map((command) => {
            const Icon = command.item.icon;
            const label = t(locale, command.titleKey ?? workspacePageLabelKey(command.pageId, activeWorkspace));
            return (
              <button
                className={cx("workspace-command-card", active === command.pageId && "active")}
                key={command.pageId}
                onClick={() => onNavigate(command.pageId)}
                onFocus={() => preloadPage?.(command.pageId)}
                onMouseEnter={() => preloadPage?.(command.pageId)}
                title={label}
                type="button"
              >
                <Icon size={17} strokeWidth={1.8} />
                <span>{label}</span>
                <small>{t(locale, command.descriptionKey)}</small>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}

const commandDefinitionsByWorkspace: Record<WorkspaceId, WorkspaceCommandDefinition[]> = {
  user: [
    {
      descriptionKey: "workspaceCommandUserAgentsDesc",
      pageId: "digitalEmployees",
    },
    {
      descriptionKey: "workspaceCommandUserMediaDesc",
      pageId: "mediaGeneration",
    },
    {
      descriptionKey: "workspaceCommandUserKnowledgeDesc",
      pageId: "knowledgeBases",
    },
  ],
  admin: [
    {
      descriptionKey: "workspaceCommandAdminAgentsDesc",
      pageId: "agents",
    },
    {
      descriptionKey: "workspaceCommandAdminModelsDesc",
      pageId: "models",
    },
    {
      descriptionKey: "workspaceCommandAdminOrgDesc",
      pageId: "departments",
    },
    {
      descriptionKey: "workspaceCommandAdminBudgetsDesc",
      pageId: "budgets",
    },
    {
      descriptionKey: "workspaceCommandAdminChannelsDesc",
      pageId: "channels",
    },
  ],
};

function workspaceCommandEyebrowKey(workspace: WorkspaceId) {
  switch (workspace) {
    case "admin":
      return "workspaceCommandAdminEyebrow";
    default:
      return "workspaceCommandUserEyebrow";
  }
}

function workspaceCommandTitleKey(workspace: WorkspaceId) {
  switch (workspace) {
    case "admin":
      return "workspaceCommandAdminTitle";
    default:
      return "workspaceCommandUserTitle";
  }
}

function storedCommandCenterCollapsed(workspace: WorkspaceId) {
  if (typeof window === "undefined") {
    return defaultCommandCenterCollapsed(workspace);
  }
  try {
    const value = window.localStorage.getItem(commandCenterStorageKey(workspace));
    if (value === "expanded") {
      return false;
    }
    if (value === "collapsed") {
      return true;
    }
  } catch {
    return defaultCommandCenterCollapsed(workspace);
  }
  return defaultCommandCenterCollapsed(workspace);
}

function saveCommandCenterCollapsed(workspace: WorkspaceId, collapsed: boolean) {
  try {
    window.localStorage.setItem(commandCenterStorageKey(workspace), collapsed ? "collapsed" : "expanded");
  } catch {
    // The command center still works in-memory when browser storage is unavailable.
  }
}

function defaultCommandCenterCollapsed(_workspace: WorkspaceId) {
  return true;
}

function commandCenterStorageKey(workspace: WorkspaceId) {
  return `agenthive.command_center.${workspace}`;
}
