import { lazy, type ReactNode, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { ApiNotice, LoadingState, ToastProvider } from "./components/app-ui";
import { AppShell } from "./components/layout/AppShell";
import { PageErrorBoundary } from "./components/PageErrorBoundary";
import type { NavItem, PageId, WorkspaceId } from "./data";
import { navItems } from "./data";
import { getStoredLocale, type Locale, saveLocale, t } from "./i18n";
import { LocaleProvider } from "./i18n-context";
import {
  type AuthUser,
  authApi,
  clearAuthToken,
  getStoredAuthUser,
  hasAuthSession,
  SESSION_EXPIRED_EVENT,
  type SetupStatusResponse,
  saveAuthToken,
} from "./lib/api";
import { canAccessRequirement, filterByPermission } from "./lib/permissions";
import { activatePrototypeMode, clearPrototypeMode, getStoredPrototypeMode } from "./lib/runtimeMode";
import {
  accessibleWorkspaceIds,
  firstVisiblePage,
  getStoredWorkspacePreference,
  navItemVisibleInWorkspace,
  preferredWorkspace,
  resolveChatNavigationPage,
  saveWorkspacePreference,
  workspaceForPage,
} from "./lib/workspaces";
import { AuthShell } from "./pages/auth/AuthShell";
import { LoginPage } from "./pages/auth/LoginPage";
import { SetupPage } from "./pages/auth/SetupPage";

const pageLoaders = {
  digitalEmployees: () => import("./pages/DigitalEmployeesPage"),
  overview: () => import("./pages/OverviewPage"),
  agents: () => import("./pages/AgentsPage"),
  agentModules: () => import("./pages/AgentModulesPage"),
  builder: () => import("./pages/BuilderPage"),
  knowledgeBases: () => import("./pages/KnowledgePage"),
  mediaGeneration: () => import("./pages/MediaPage"),
  chatConsole: () => import("./pages/ChatPage"),
  channels: () => import("./pages/ChannelsPage"),
  models: () => import("./pages/ModelsPage"),
  budgets: () => import("./pages/BudgetsPage"),
  departments: () => import("./pages/DepartmentsPage"),
  users: () => import("./pages/UsersPage"),
  auditLogs: () => import("./pages/AuditPage"),
  license: () => import("./pages/LicensePage"),
  settings: () => import("./pages/SettingsPage"),
} satisfies Record<PageId, () => Promise<unknown>>;

const DigitalEmployeesPage = lazy(() =>
  pageLoaders.digitalEmployees().then(({ DigitalEmployeesPage }) => ({ default: DigitalEmployeesPage })),
);
const OverviewPage = lazy(() => pageLoaders.overview().then(({ OverviewPage }) => ({ default: OverviewPage })));
const AgentsPage = lazy(() => pageLoaders.agents().then(({ AgentsPage }) => ({ default: AgentsPage })));
const AgentModulesPage = lazy(() =>
  pageLoaders.agentModules().then(({ AgentModulesPage }) => ({ default: AgentModulesPage })),
);
const BuilderPage = lazy(() => pageLoaders.builder().then(({ BuilderPage }) => ({ default: BuilderPage })));
const KnowledgePage = lazy(() =>
  pageLoaders.knowledgeBases().then(({ KnowledgePage }) => ({ default: KnowledgePage })),
);
const MediaPage = lazy(() => pageLoaders.mediaGeneration().then(({ MediaPage }) => ({ default: MediaPage })));
const ChatPage = lazy(() => pageLoaders.chatConsole().then(({ ChatPage }) => ({ default: ChatPage })));
const ChannelsPage = lazy(() => pageLoaders.channels().then(({ ChannelsPage }) => ({ default: ChannelsPage })));
const ModelsPage = lazy(() => pageLoaders.models().then(({ ModelsPage }) => ({ default: ModelsPage })));
const BudgetsPage = lazy(() => pageLoaders.budgets().then(({ BudgetsPage }) => ({ default: BudgetsPage })));
const DepartmentsPage = lazy(() =>
  pageLoaders.departments().then(({ DepartmentsPage }) => ({ default: DepartmentsPage })),
);
const UsersPage = lazy(() => pageLoaders.users().then(({ UsersPage }) => ({ default: UsersPage })));
const AuditPage = lazy(() => pageLoaders.auditLogs().then(({ AuditPage }) => ({ default: AuditPage })));
const LicensePage = lazy(() => pageLoaders.license().then(({ LicensePage }) => ({ default: LicensePage })));
const SettingsPage = lazy(() => pageLoaders.settings().then(({ SettingsPage }) => ({ default: SettingsPage })));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage").then(({ NotFoundPage }) => ({ default: NotFoundPage })));
export function App() {
  const [active, setActive] = useState<PageId>("digitalEmployees");
  const [activeWorkspace, setActiveWorkspaceState] = useState<WorkspaceId>(
    () => getStoredWorkspacePreference() ?? "user",
  );
  const [workspaceBootstrapped, setWorkspaceBootstrapped] = useState(false);
  const [locale, setLocaleState] = useState<Locale>(() => getStoredLocale());
  const [authState, setAuthState] = useState<
    "checking" | "unavailable" | "setup" | "login" | "authenticated" | "prototype"
  >(() => (getStoredPrototypeMode() ? "prototype" : "checking"));
  const [authUser, setAuthUser] = useState<AuthUser | null>(() => getStoredAuthUser());
  const [authError, setAuthError] = useState<string | null>(null);
  const [setupStatus, setSetupStatus] = useState<SetupStatusResponse | null>(null);
  const commonSessionExpired = t(locale, "commonSessionExpired");
  const commonSetupStatusFailed = t(locale, "commonSetupStatusFailed");

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  useEffect(() => {
    const handleSessionExpired = () => {
      clearPrototypeMode();
      setAuthUser(null);
      setAuthError(commonSessionExpired);
      setAuthState("login");
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
    return () => {
      window.removeEventListener(SESSION_EXPIRED_EVENT, handleSessionExpired);
    };
  }, [commonSessionExpired]);

  useEffect(() => {
    if (authState !== "checking") {
      return;
    }
    let cancelled = false;
    authApi
      .getSetupStatus()
      .then((status) => {
        if (cancelled) {
          return;
        }
        setSetupStatus(status);
        if (!status.setup_available) {
          clearAuthToken();
          setAuthUser(null);
          setAuthError(status.message || commonSetupStatusFailed);
          setAuthState("setup");
          return;
        }
        if (!status.initialized) {
          clearAuthToken();
          setAuthUser(null);
          setAuthState("setup");
          setAuthError(null);
          return;
        }
        if (hasAuthSession()) {
          authApi
            .refresh()
            .then((auth) => {
              if (cancelled) {
                return;
              }
              saveAuthToken(auth);
              setAuthUser(auth.user);
              setAuthState("authenticated");
              setAuthError(null);
            })
            .catch((caught) => {
              if (cancelled) {
                return;
              }
              clearAuthToken();
              setAuthUser(null);
              setAuthError(caught instanceof Error ? caught.message : commonSessionExpired);
              setAuthState("login");
            });
          return;
        }
        setAuthState("login");
        setAuthError(null);
      })
      .catch((caught) => {
        if (cancelled) {
          return;
        }
        setSetupStatus(null);
        setAuthError(caught instanceof Error ? caught.message : commonSetupStatusFailed);
        // Cached display metadata and the readable CSRF cookie are not proof
        // of an authenticated server session. Fail closed until setup status
        // can be read and refresh has confirmed the HttpOnly session cookie.
        setAuthState("unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, [authState, commonSessionExpired, commonSetupStatusFailed]);

  const isPrototype = authState === "prototype";
  const permittedNavItems = useMemo(
    () => (isPrototype ? navItems : filterByPermission(navItems, authUser)),
    [authUser, isPrototype],
  );
  const isNavItemVisibleInWorkspace = useCallback(
    (item: NavItem, workspace: WorkspaceId) => navItemVisibleInWorkspace(item, workspace, authUser, isPrototype),
    [authUser, isPrototype],
  );
  const visibleNavItems = useMemo(
    () => permittedNavItems.filter((item) => isNavItemVisibleInWorkspace(item, activeWorkspace)),
    [activeWorkspace, isNavItemVisibleInWorkspace, permittedNavItems],
  );
  const accessibleWorkspaces = useMemo(
    () => accessibleWorkspaceIds(permittedNavItems, isNavItemVisibleInWorkspace),
    [isNavItemVisibleInWorkspace, permittedNavItems],
  );
  const activeNavItem = useMemo(() => navItems.find((item) => item.id === active), [active]);
  const canRenderActivePage =
    (isPrototype || canAccessRequirement(authUser, activeNavItem)) &&
    visibleNavItems.some((item) => item.id === active);
  const hasVisibleWorkspace = visibleNavItems.length > 0;

  const setActiveWorkspace = useCallback((workspace: WorkspaceId) => {
    saveWorkspacePreference(workspace);
    setActiveWorkspaceState(workspace);
  }, []);

  const navigateToPage = useCallback(
    (pageId: PageId) => {
      const resolvedPageId = resolveChatNavigationPage(pageId, permittedNavItems, isNavItemVisibleInWorkspace);
      const targetWorkspace = workspaceForPage(
        permittedNavItems,
        resolvedPageId,
        activeWorkspace,
        isNavItemVisibleInWorkspace,
      );
      if (targetWorkspace !== activeWorkspace) {
        setActiveWorkspace(targetWorkspace);
      }
      setActive(resolvedPageId);
    },
    [activeWorkspace, isNavItemVisibleInWorkspace, permittedNavItems, setActiveWorkspace],
  );

  useEffect(() => {
    if (!["authenticated", "prototype"].includes(authState) || workspaceBootstrapped) {
      return;
    }
    const preferred = preferredWorkspace(permittedNavItems, isNavItemVisibleInWorkspace);
    setWorkspaceBootstrapped(true);
    if (!preferred) {
      return;
    }
    setActiveWorkspace(preferred);
    setActive(firstVisiblePage(permittedNavItems, preferred, isNavItemVisibleInWorkspace));
  }, [authState, isNavItemVisibleInWorkspace, permittedNavItems, setActiveWorkspace, workspaceBootstrapped]);

  useEffect(() => {
    if (!["authenticated", "prototype"].includes(authState) || canRenderActivePage) {
      return;
    }
    const resolvedActive = resolveChatNavigationPage(active, permittedNavItems, isNavItemVisibleInWorkspace);
    if (resolvedActive !== active) {
      setActive(resolvedActive);
      return;
    }
    const fallbackPage = firstVisiblePage(permittedNavItems, activeWorkspace, isNavItemVisibleInWorkspace);
    if (fallbackPage && active !== fallbackPage) {
      setActive(fallbackPage);
    }
  }, [active, activeWorkspace, authState, canRenderActivePage, isNavItemVisibleInWorkspace, permittedNavItems]);

  useEffect(() => {
    if (!["authenticated", "prototype"].includes(authState)) {
      return;
    }
    if (visibleNavItems.length > 0 || accessibleWorkspaces.length === 0) {
      return;
    }
    setActiveWorkspace(accessibleWorkspaces[0]);
  }, [accessibleWorkspaces, authState, setActiveWorkspace, visibleNavItems.length]);

  const content = useMemo(() => {
    if (authState === "authenticated" && !hasVisibleWorkspace) {
      return <NoAccessibleWorkspace locale={locale} />;
    }
    if (authState === "authenticated" && !canRenderActivePage) {
      return <PageLoading locale={locale} />;
    }
    switch (active) {
      case "digitalEmployees":
        return <DigitalEmployeesPage user={authUser} isPrototype={isPrototype} />;
      case "overview":
        return <OverviewPage activeWorkspace={activeWorkspace} isPrototype={isPrototype} onNavigate={navigateToPage} />;
      case "agents":
        return (
          <AgentsPage
            activeWorkspace={activeWorkspace}
            user={authUser}
            isPrototype={isPrototype}
            onNavigate={navigateToPage}
          />
        );
      case "agentModules":
        return <AgentModulesPage isPrototype={isPrototype} onNavigate={navigateToPage} />;
      case "builder":
        return <BuilderPage isPrototype={isPrototype} user={authUser} />;
      case "knowledgeBases":
        return (
          <KnowledgePage
            activeWorkspace={activeWorkspace}
            user={authUser}
            isPrototype={isPrototype}
            onNavigate={navigateToPage}
          />
        );
      case "mediaGeneration":
        return <MediaPage activeWorkspace={activeWorkspace} isPrototype={isPrototype} />;
      case "chatConsole":
        return <ChatPage user={authUser} isPrototype={isPrototype} />;
      case "models":
        return <ModelsPage activeWorkspace={activeWorkspace} user={authUser} isPrototype={isPrototype} />;
      case "budgets":
        return <BudgetsPage activeWorkspace={activeWorkspace} user={authUser} isPrototype={isPrototype} />;
      case "departments":
        return <DepartmentsPage activeWorkspace={activeWorkspace} isPrototype={isPrototype} />;
      case "users":
        return <UsersPage isPrototype={isPrototype} />;
      case "auditLogs":
        return <AuditPage user={authUser} isPrototype={isPrototype} />;
      case "license":
        return <LicensePage user={authUser} isPrototype={isPrototype} />;
      case "channels":
        return <ChannelsPage activeWorkspace={activeWorkspace} user={authUser} isPrototype={isPrototype} />;
      case "settings":
        return <SettingsPage user={authUser} isPrototype={isPrototype} />;
      default:
        return <NotFoundPage onGoHome={() => setActive("digitalEmployees")} />;
    }
  }, [
    active,
    activeWorkspace,
    authState,
    authUser,
    canRenderActivePage,
    hasVisibleWorkspace,
    isPrototype,
    locale,
    navigateToPage,
  ]);

  const authenticate = () => {
    clearPrototypeMode();
    setAuthError(null);
    setAuthUser(getStoredAuthUser());
    setWorkspaceBootstrapped(false);
    setAuthState("authenticated");
  };

  const usePrototypeMode = () => {
    if (!activatePrototypeMode()) {
      return;
    }
    setAuthError(null);
    setAuthUser(null);
    setWorkspaceBootstrapped(false);
    setAuthState("prototype");
  };

  const logout = () => {
    const finishLogout = () => {
      clearPrototypeMode();
      clearAuthToken();
      setAuthUser(null);
      setWorkspaceBootstrapped(false);
      setAuthState("login");
    };
    if (hasAuthSession()) {
      void authApi.logout().finally(finishLogout);
      return;
    }
    finishLogout();
  };

  const setLocale = useCallback((nextLocale: Locale) => {
    setLocaleState(nextLocale);
    saveLocale(nextLocale);
  }, []);

  const preloadPage = useCallback((pageId: PageId) => {
    void pageLoaders[pageId]();
  }, []);

  const withLocale = (node: ReactNode) => (
    <LocaleProvider locale={locale} setLocale={setLocale}>
      <ToastProvider>{node}</ToastProvider>
    </LocaleProvider>
  );

  if (authState === "checking") {
    return withLocale(
      <AuthShell>
        <ApiNotice title={t(locale, "commonCheckingDeployment")} message={t(locale, "commonReadingSetupStatus")} />
      </AuthShell>,
    );
  }

  if (authState === "setup") {
    return withLocale(
      <SetupPage
        error={authError}
        onComplete={authenticate}
        onPrototype={usePrototypeMode}
        setupStatus={setupStatus}
      />,
    );
  }

  if (authState === "unavailable") {
    return withLocale(
      <AuthShell>
        <ApiNotice
          title={commonSetupStatusFailed}
          message={authError ?? commonSetupStatusFailed}
          onRetry={() => {
            setAuthError(null);
            setAuthState("checking");
          }}
        />
      </AuthShell>,
    );
  }

  if (authState === "login") {
    return withLocale(<LoginPage error={authError} onComplete={authenticate} onPrototype={usePrototypeMode} />);
  }

  return withLocale(
    <AppShell
      active={active}
      setActive={setActive}
      locale={locale}
      setLocale={setLocale}
      onLogout={logout}
      authUser={authUser}
      isPrototype={isPrototype}
      preloadPage={preloadPage}
      activeWorkspace={activeWorkspace}
      setActiveWorkspace={setActiveWorkspace}
    >
      <PageErrorBoundary
        fallbackMessage={t(locale, "pageRenderErrorMessage")}
        fallbackTitle={t(locale, "pageRenderErrorTitle")}
        resetKey={`${active}:${locale}`}
        resetLabel={t(locale, "pageReload")}
      >
        <Suspense fallback={<PageLoading locale={locale} />}>{content}</Suspense>
      </PageErrorBoundary>
    </AppShell>,
  );
}

function PageLoading({ locale }: { locale: Locale }) {
  return (
    <section className="page page-loading">
      <LoadingState message={t(locale, "commonPageLoadingMessage")} />
    </section>
  );
}

function NoAccessibleWorkspace({ locale }: { locale: Locale }) {
  return (
    <section className="page page-loading">
      <ApiNotice title={t(locale, "commonNoWorkspaceTitle")} message={t(locale, "commonNoWorkspaceMessage")} />
    </section>
  );
}
