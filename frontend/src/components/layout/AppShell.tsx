import {
  Bell,
  BriefcaseBusiness,
  Globe2,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  ShieldCheck,
  UserCircle,
  X,
} from "lucide-react";
import type { ReactNode } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { navItems, type PageId, type WorkspaceId } from "../../data";
import { useWorkbenchAgentInstances } from "../../hooks/admin/agents";
import { type Locale, t } from "../../i18n";
import type { AuthUser } from "../../lib/api";
import { canAccess, filterByPermission } from "../../lib/permissions";
import {
  firstVisiblePage,
  navItemVisibleInWorkspace,
  workspacePageLabelKey,
  workspaceProfile,
  workspaceProfiles,
} from "../../lib/workspaces";
import { cx } from "../app-ui";
import { WorkspaceCommandCenter } from "./WorkspaceCommandCenter";
import { WorkspaceNavigation } from "./WorkspaceNavigation";

export function AppShell({
  active,
  setActive,
  locale,
  setLocale,
  onLogout,
  authUser,
  isPrototype,
  preloadPage,
  activeWorkspace,
  setActiveWorkspace,
  children,
}: {
  active: PageId;
  setActive: (id: PageId) => void;
  locale: Locale;
  setLocale: (locale: Locale) => void;
  onLogout: () => void;
  authUser: AuthUser | null;
  isPrototype: boolean;
  preloadPage?: (id: PageId) => void;
  activeWorkspace: WorkspaceId;
  setActiveWorkspace: (id: WorkspaceId) => void;
  children: ReactNode;
}) {
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [hasUnreadNotifications, setHasUnreadNotifications] = useState(false);
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => window.localStorage.getItem("agenthive.sidebar") === "collapsed",
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState(() =>
    window.sessionStorage.getItem("agenthive.selected_agent_id"),
  );
  const notificationRef = useRef<HTMLDivElement | null>(null);
  const navigationRef = useRef<HTMLElement | null>(null);
  const mobileNavigationToggleRef = useRef<HTMLButtonElement | null>(null);
  const searchRef = useRef<HTMLDivElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const { data: agentInstances } = useWorkbenchAgentInstances({ fallbackOnError: isPrototype });
  const permittedNav = isPrototype ? navItems : filterByPermission(navItems, authUser);
  const visibleNav = permittedNav.filter((item) =>
    navItemVisibleInWorkspace(item, activeWorkspace, authUser, isPrototype),
  );
  const mainNav = visibleNav.filter(
    (item) => item.id !== "digitalEmployees" && !(item.id === "settings" && activeWorkspace !== "admin"),
  );
  const settings = activeWorkspace === "admin" ? undefined : visibleNav.find((item) => item.id === "settings");
  const workbenchNav = visibleNav.find((item) => item.id === "digitalEmployees");
  const activeAgents = useMemo(
    () => (agentInstances ?? []).filter((instance) => instance.status === "active"),
    [agentInstances],
  );
  const trimmedSearch = searchQuery.trim().toLowerCase();
  const searchResults = useMemo(() => {
    if (!trimmedSearch) {
      return [];
    }
    return visibleNav.filter((item) =>
      t(locale, workspacePageLabelKey(item.id, activeWorkspace)).toLowerCase().includes(trimmedSearch),
    );
  }, [activeWorkspace, locale, trimmedSearch, visibleNav]);
  const notifications = notificationDefinitions
    .filter((item) => item.workspaces.includes(activeWorkspace))
    .filter((item) => isPrototype || canAccess(authUser, item.requiredAnyPermission, item.requiredAllPermission))
    .map((item) => ({
      title: t(locale, item.titleKey),
      message: t(locale, item.messageKey),
      meta: t(locale, item.metaKey),
    }));
  const currentWorkspace = workspaceProfile(activeWorkspace);
  const workspaceOptions = useMemo(
    () =>
      workspaceProfiles
        .filter((workspace) => permittedNav.some((item) => item.workspaces.includes(workspace.id)))
        .filter((workspace) =>
          permittedNav.some((item) => navItemVisibleInWorkspace(item, workspace.id, authUser, isPrototype)),
        )
        .map((workspace) => ({
          id: workspace.id,
          label: t(locale, workspace.labelKey),
          description: t(locale, workspace.descriptionKey),
          icon: workspaceIcon(workspace.id),
        })),
    [authUser, isPrototype, locale, permittedNav],
  );
  const showWorkspaceSwitcher = workspaceOptions.length > 1;
  const currentWorkspaceOption =
    workspaceOptions.find((workspace) => workspace.id === activeWorkspace) ?? workspaceOptions[0];
  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((collapsed) => {
      const next = !collapsed;
      window.localStorage.setItem("agenthive.sidebar", next ? "collapsed" : "expanded");
      return next;
    });
  }, []);
  const closeFloatingPanels = useCallback(() => {
    setNotificationsOpen(false);
    setSearchQuery("");
  }, []);
  const closeMobileNavigation = useCallback(() => {
    setMobileNavigationOpen(false);
    window.requestAnimationFrame(() => mobileNavigationToggleRef.current?.focus());
  }, []);
  const navigateTo = useCallback(
    (pageId: PageId) => {
      closeFloatingPanels();
      setMobileNavigationOpen(false);
      setActive(pageId);
      window.requestAnimationFrame(() => document.getElementById("main-content")?.focus());
    },
    [closeFloatingPanels, setActive],
  );
  const navigateToAgent = useCallback(
    (agentId: string) => {
      window.sessionStorage.setItem("agenthive.selected_agent_id", agentId);
      setSelectedAgentId(agentId);
      window.dispatchEvent(new CustomEvent("agenthive:selected-agent", { detail: { agentId } }));
      navigateTo("digitalEmployees");
    },
    [navigateTo],
  );
  const switchWorkspace = useCallback(
    (workspaceId: WorkspaceId) => {
      closeFloatingPanels();
      setMobileNavigationOpen(false);
      setActiveWorkspace(workspaceId);
      const activeInWorkspace = permittedNav.some(
        (item) => item.id === active && navItemVisibleInWorkspace(item, workspaceId, authUser, isPrototype),
      );
      if (!activeInWorkspace) {
        setActive(
          firstVisiblePage(
            permittedNav.filter((item) => navItemVisibleInWorkspace(item, workspaceId, authUser, isPrototype)),
            workspaceId,
          ),
        );
      }
    },
    [active, authUser, closeFloatingPanels, isPrototype, permittedNav, setActive, setActiveWorkspace],
  );

  useEffect(() => {
    const handleSelectedAgent = (event: Event) => {
      const agentId = event instanceof CustomEvent ? event.detail?.agentId : null;
      if (typeof agentId === "string") {
        setSelectedAgentId(agentId);
      }
    };
    window.addEventListener("agenthive:selected-agent", handleSelectedAgent);
    return () => window.removeEventListener("agenthive:selected-agent", handleSelectedAgent);
  }, []);

  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) {
        return;
      }
      if (notificationsOpen && !notificationRef.current?.contains(target)) {
        setNotificationsOpen(false);
      }
      if (searchQuery && !searchRef.current?.contains(target)) {
        setSearchQuery("");
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeFloatingPanels();
        if (mobileNavigationOpen) {
          closeMobileNavigation();
        }
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [closeFloatingPanels, closeMobileNavigation, mobileNavigationOpen, notificationsOpen, searchQuery]);

  useEffect(() => {
    if (!mobileNavigationOpen) {
      return;
    }
    const getFocusableNavigationElements = () =>
      Array.from(navigationRef.current?.querySelectorAll<HTMLElement>("button:not([disabled]), [href]") ?? []).filter(
        (element) => element.offsetParent !== null,
      );
    const focusable = getFocusableNavigationElements();
    const focusTimer = window.setTimeout(() => focusable[0]?.focus(), 0);
    const trapFocus = (event: KeyboardEvent) => {
      if (event.key !== "Tab") {
        return;
      }
      const items = getFocusableNavigationElements();
      if (!items.length) {
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", trapFocus);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener("keydown", trapFocus);
    };
  }, [mobileNavigationOpen]);

  useEffect(() => {
    const handleSearchShortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && (event.key === "k" || event.key === "K")) {
        event.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    document.addEventListener("keydown", handleSearchShortcut);
    return () => document.removeEventListener("keydown", handleSearchShortcut);
  }, []);

  return (
    <div
      className={cx(
        "app-shell",
        sidebarCollapsed && "sidebar-collapsed",
        mobileNavigationOpen && "mobile-navigation-open",
      )}
    >
      <a href="#main-content" className="skip-link">
        {t(locale, "commonSkipToMainContent")}
      </a>
      {mobileNavigationOpen && (
        <button
          type="button"
          className="mobile-navigation-backdrop"
          aria-label={t(locale, "commonCloseMenu")}
          onClick={closeMobileNavigation}
        />
      )}
      <nav ref={navigationRef} id="primary-navigation" className="sidebar" aria-label={t(locale, "commonSidebarNav")}>
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">
            ✣
          </div>
          <div className="brand-copy">
            <strong>AgentHive</strong>
            <span>{t(locale, "commonProductTagline")}</span>
          </div>
          <button
            type="button"
            className="sidebar-collapse-button"
            aria-label={t(locale, sidebarCollapsed ? "sidebarExpand" : "sidebarCollapse")}
            aria-expanded={!sidebarCollapsed}
            aria-controls="primary-navigation"
            title={t(locale, sidebarCollapsed ? "sidebarExpand" : "sidebarCollapse")}
            onClick={toggleSidebar}
          >
            {sidebarCollapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
          </button>
        </div>
        {showWorkspaceSwitcher ? (
          <fieldset className="workspace-switcher">
            <legend>{t(locale, "workspaceSwitcher")}</legend>
            {workspaceOptions.map((workspace) => (
              <button
                key={workspace.id}
                type="button"
                className={cx("workspace-tab", activeWorkspace === workspace.id && "active")}
                aria-pressed={activeWorkspace === workspace.id}
                title={workspace.description}
                onClick={() => switchWorkspace(workspace.id)}
              >
                <workspace.icon size={15} strokeWidth={1.8} />
                <span>{workspace.label}</span>
                <small>{workspace.description}</small>
              </button>
            ))}
          </fieldset>
        ) : currentWorkspaceOption ? (
          <div className="workspace-current-view" title={currentWorkspaceOption.description}>
            <currentWorkspaceOption.icon size={15} strokeWidth={1.8} />
            <span>{t(locale, "workspaceCurrentView")}</span>
            <strong>{currentWorkspaceOption.label}</strong>
            <small>{currentWorkspaceOption.description}</small>
          </div>
        ) : null}
        <WorkspaceNavigation
          active={active}
          activeAgents={activeAgents}
          activeWorkspace={activeWorkspace}
          locale={locale}
          mainNav={mainNav}
          onNavigate={navigateTo}
          onNavigateAgent={navigateToAgent}
          preloadPage={preloadPage}
          selectedAgentId={selectedAgentId}
          settings={settings}
          workbenchNav={workbenchNav}
        />
      </nav>
      <div className="workspace">
        <header className="topbar">
          <button
            type="button"
            ref={mobileNavigationToggleRef}
            className="mobile-navigation-toggle"
            aria-controls="primary-navigation"
            aria-expanded={mobileNavigationOpen}
            aria-label={t(locale, mobileNavigationOpen ? "commonCloseMenu" : "commonSidebarNav")}
            title={t(locale, mobileNavigationOpen ? "commonCloseMenu" : "commonSidebarNav")}
            onClick={() => {
              if (mobileNavigationOpen) {
                closeMobileNavigation();
                return;
              }
              setMobileNavigationOpen(true);
            }}
          >
            {mobileNavigationOpen ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
          </button>
          <div className="workspace-context">
            <strong>{t(locale, currentWorkspace.labelKey)}</strong>
            <span>{t(locale, currentWorkspace.descriptionKey)}</span>
          </div>
          <div className="topbar-search" ref={searchRef}>
            <div className="searchbox">
              <Search size={18} aria-hidden="true" />
              <input
                ref={searchInputRef}
                aria-label={t(locale, "search")}
                placeholder={`${t(locale, "search")} (⌘K)`}
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    setSearchQuery("");
                    searchInputRef.current?.blur();
                  }
                  if (event.key === "Enter" && searchResults[0]) {
                    navigateTo(searchResults[0].id);
                    setSearchQuery("");
                  }
                }}
              />
            </div>
            {trimmedSearch && (
              <div className="search-results-panel" role="listbox" aria-label={t(locale, "search")}>
                {searchResults.length ? (
                  searchResults.map((item) => {
                    const Icon = item.icon;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        role="option"
                        aria-selected="false"
                        onClick={() => {
                          navigateTo(item.id);
                          setSearchQuery("");
                        }}
                      >
                        <Icon size={16} aria-hidden="true" />
                        <span>{t(locale, workspacePageLabelKey(item.id, activeWorkspace))}</span>
                        <small className="search-result-action">{t(locale, "searchGoTo")}</small>
                      </button>
                    );
                  })
                ) : (
                  <div className="search-empty">{t(locale, "searchNoResults")}</div>
                )}
              </div>
            )}
          </div>
          <div className="top-actions">
            <button
              type="button"
              className="icon-button"
              onClick={() => setLocale(locale === "en-US" ? "zh-CN" : "en-US")}
              aria-label={t(locale, "language")}
              aria-haspopup="listbox"
              title={t(locale, "language")}
            >
              <Globe2 size={21} aria-hidden="true" />
            </button>
            <div className="top-action-item" ref={notificationRef}>
              <button
                type="button"
                className={cx(
                  "icon-button",
                  hasUnreadNotifications && notifications.length > 0 && "has-dot",
                  notificationsOpen && "active",
                )}
                aria-expanded={notificationsOpen}
                aria-haspopup="dialog"
                aria-controls="notifications-panel"
                aria-label={t(locale, "notifications")}
                title={t(locale, "notifications")}
                onClick={() => setNotificationsOpen((open) => !open)}
              >
                <Bell size={21} aria-hidden="true" />
              </button>
              {notificationsOpen && (
                <>
                  <div className="notification-dismiss-layer" onPointerDown={() => setNotificationsOpen(false)} />
                  <div
                    className="notification-panel"
                    id="notifications-panel"
                    role="dialog"
                    aria-modal="false"
                    aria-label={t(locale, "notifications")}
                  >
                    <div className="notification-panel-head">
                      <strong>{t(locale, "notifications")}</strong>
                      <button
                        type="button"
                        className="text-button"
                        onClick={() => {
                          setHasUnreadNotifications(false);
                          setNotificationsOpen(false);
                        }}
                      >
                        {t(locale, "notificationsMarkRead")}
                      </button>
                    </div>
                    <div className="notification-list">
                      {notifications.length ? (
                        notifications.map((item) => (
                          <article className="notification-item" key={item.title}>
                            <strong>{item.title}</strong>
                            <p>{item.message}</p>
                            <span>{item.meta}</span>
                          </article>
                        ))
                      ) : (
                        <div className="notification-empty">{t(locale, "notificationsEmpty")}</div>
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>
            <button
              type="button"
              className="icon-button"
              aria-label={t(locale, "signOut")}
              title={t(locale, "signOut")}
              onClick={onLogout}
            >
              <UserCircle size={22} aria-hidden="true" />
            </button>
          </div>
        </header>
        {isPrototype && (
          <section className="runtime-mode-banner" aria-label={t(locale, "runtimePrototypeTitle")}>
            <div>
              <strong>{t(locale, "runtimePrototypeTitle")}</strong>
              <span>{t(locale, "runtimePrototypeMessage")}</span>
            </div>
            <button type="button" className="text-button runtime-mode-exit" onClick={onLogout}>
              {t(locale, "runtimePrototypeExit")}
            </button>
          </section>
        )}
        <WorkspaceCommandCenter
          active={active}
          activeWorkspace={activeWorkspace}
          locale={locale}
          onNavigate={navigateTo}
          preloadPage={preloadPage}
          visibleNav={visibleNav}
        />
        <main id="main-content" className="main-canvas" tabIndex={-1} aria-label={t(locale, "commonMainMenu")}>
          {children}
        </main>
      </div>
    </div>
  );
}

interface NotificationDefinition {
  titleKey: string;
  messageKey: string;
  metaKey: string;
  workspaces: WorkspaceId[];
  requiredAnyPermission?: string[];
  requiredAllPermission?: string[];
}

const notificationDefinitions: NotificationDefinition[] = [
  {
    titleKey: "notificationAgentReadyTitle",
    messageKey: "notificationAgentReadyMessage",
    metaKey: "notificationAgentReadyMeta",
    workspaces: ["user"],
    requiredAnyPermission: ["agents:read", "chat:write"],
  },
  {
    titleKey: "notificationTaskResultTitle",
    messageKey: "notificationTaskResultMessage",
    metaKey: "notificationTaskResultMeta",
    workspaces: ["user"],
    requiredAnyPermission: ["chat:read", "chat:write"],
  },
  {
    titleKey: "notificationUsageTitle",
    messageKey: "notificationUsageMessage",
    metaKey: "notificationUsageMeta",
    workspaces: ["user"],
    requiredAnyPermission: ["chat:read", "chat:write"],
  },
  {
    titleKey: "notificationDeliveryTitle",
    messageKey: "notificationDeliveryMessage",
    metaKey: "notificationDeliveryMeta",
    workspaces: ["admin"],
    requiredAnyPermission: ["system:diagnostics", "license:read"],
  },
  {
    titleKey: "notificationBudgetTitle",
    messageKey: "notificationBudgetMessage",
    metaKey: "notificationBudgetMeta",
    workspaces: ["admin"],
    requiredAnyPermission: ["budgets:read", "budgets:write"],
  },
  {
    titleKey: "notificationLicenseTitle",
    messageKey: "notificationLicenseMessage",
    metaKey: "notificationLicenseMeta",
    workspaces: ["admin"],
    requiredAnyPermission: ["license:read", "license:write"],
  },
];

function workspaceIcon(workspace: WorkspaceId) {
  switch (workspace) {
    case "admin":
      return ShieldCheck;
    default:
      return BriefcaseBusiness;
  }
}
