import { ArrowLeft, Search } from "lucide-react";
import { ApiNotice, Button, cx, LoadingState, PageHeader, PageTabs } from "../components/app-ui";
import type { PageId } from "../data";
import { useLocale } from "../i18n-context";
import { ModuleActionQueue } from "./agent-modules/ModuleActionQueue";
import { ModuleCard } from "./agent-modules/ModuleCard";
import { ModuleDetailsPanel } from "./agent-modules/ModuleDetailsPanel";
import { ModuleFilters } from "./agent-modules/ModuleFilters";
import { useAgentModulesController } from "./agent-modules/useAgentModulesController";

export function AgentModulesPage({
  isPrototype = false,
  onNavigate,
}: {
  isPrototype?: boolean;
  onNavigate?: (page: PageId) => void;
}) {
  const { t } = useLocale();
  const modules = useAgentModulesController({ isPrototype, onNavigate });

  return (
    <section className="page modules-layout">
      <ModuleFilters
        categories={modules.categories}
        category={modules.category}
        licenseFilter={modules.licenseFilter}
        setCategory={modules.setCategory}
        setLicenseFilter={modules.setLicenseFilter}
        setStateFilter={modules.setStateFilter}
        stateFilter={modules.stateFilter}
        stateOptions={modules.stateOptions}
      />
      <div className="modules-main">
        <PageHeader
          title={t("modulesMarketplaceTitle")}
          actions={
            modules.moduleWorkspace === "catalog" ? (
              <div className="searchbox embedded">
                <Search size={18} />
                <input
                  placeholder={t("modulesSearchPlaceholder")}
                  value={modules.query}
                  onChange={(event) => modules.setQuery(event.target.value)}
                />
              </div>
            ) : (
              <Button onClick={() => modules.setModuleWorkspace("catalog")}>
                <ArrowLeft size={16} /> {t("modulesBackToCatalog")}
              </Button>
            )
          }
        />
        <PageTabs
          active={modules.moduleWorkspace}
          onChange={modules.setModuleWorkspace}
          tabs={[
            {
              id: "catalog",
              label: t("modulesWorkspaceCatalog"),
              description: t("modulesWorkspaceCatalogDesc"),
            },
            {
              id: "details",
              label: t("modulesWorkspaceDetails"),
              description: modules.selectedModule
                ? t("modulesWorkspaceDetailsSelected").replace("{{name}}", modules.selectedModule.name)
                : t("modulesWorkspaceDetailsDesc"),
            },
          ]}
        />
        {modules.loading && !modules.visibleModules.length && (
          <LoadingState message={t("modulesLoadingMessage")} lines={3} />
        )}
        {modules.loading && !!modules.visibleModules.length && (
          <div className="refresh-indicator" role="status" aria-live="polite">
            <span className="refresh-spinner" aria-hidden="true" />
            {t("commonRefreshing")}
          </div>
        )}
        {modules.error && !modules.loading && (
          <ApiNotice
            title={t("modulesLoadErrorTitle")}
            message={modules.error}
            action={<Button onClick={modules.refetch}>{t("commonRetry")}</Button>}
          />
        )}
        {!modules.loading && !modules.error && modules.visibleModules.length === 0 && (
          <ApiNotice
            title={t("modulesEmptyTitle")}
            message={modules.query ? t("modulesNoFilterMatch") : t("modulesEmptyCatalog")}
          />
        )}
        {(modules.actions.message || modules.actions.error) && (
          <div className={cx("form-message", modules.actions.error ? "error" : false)}>
            {modules.actions.error ?? modules.actions.message}
          </div>
        )}
        {modules.localNotice && <div className="form-message">{modules.localNotice}</div>}
        {modules.moduleWorkspace === "catalog" && (
          <div className="module-catalog-workspace">
            <div className="module-summary-strip">
              <span>
                {modules.catalog.length} {t("modulesTotal")}
              </span>
              <span>
                {modules.catalog.filter((module) => module.licensed).length} {t("modulesLicensedCount")}
              </span>
              <span>
                {modules.catalog.filter((module) => module.enabled).length} {t("modulesEnabledCount")}
              </span>
              <span>
                {modules.visibleModules.length} {t("modulesVisibleCount")}
              </span>
            </div>
            <ModuleActionQueue
              busyModuleId={modules.actions.busyModuleId}
              modules={modules.catalog}
              onAction={modules.runModuleAction}
              onConfigure={modules.openAgentConfiguration}
              onRequestLicense={modules.requestLicense}
              onSelect={modules.selectModule}
            />
            <PageTabs
              active={modules.moduleView}
              onChange={modules.setModuleView}
              tabs={[
                {
                  id: "all",
                  label: `${t("modulesViewAll")} ${modules.moduleViewCounts.all}`,
                  description: t("modulesViewAllDesc"),
                },
                {
                  id: "enabled",
                  label: `${t("modulesViewEnabled")} ${modules.moduleViewCounts.enabled}`,
                  description: t("modulesViewEnabledDesc"),
                },
                {
                  id: "available",
                  label: `${t("modulesViewAvailable")} ${modules.moduleViewCounts.available}`,
                  description: t("modulesViewAvailableDesc"),
                },
                {
                  id: "needs_action",
                  label: `${t("modulesViewNeedsAction")} ${modules.moduleViewCounts.needs_action}`,
                  description: t("modulesViewNeedsActionDesc"),
                },
              ]}
            />
            <div className="module-grid">
              {!modules.loading &&
                !modules.error &&
                modules.visibleModules.map((module) => (
                  <ModuleCard
                    busy={modules.actions.busyModuleId === module.id}
                    key={module.id}
                    module={module}
                    onAction={modules.runModuleAction}
                    onConfigure={modules.openAgentConfiguration}
                    onRequestLicense={modules.requestLicense}
                    onSelect={modules.selectModule}
                    selected={modules.selectedModule?.id === module.id}
                  />
                ))}
            </div>
          </div>
        )}
        {modules.moduleWorkspace === "details" && (
          <ModuleDetailsPanel
            busy={modules.selectedModule ? modules.actions.busyModuleId === modules.selectedModule.id : false}
            module={modules.selectedModule}
            onAction={modules.runModuleAction}
            onConfigure={modules.openAgentConfiguration}
            onRequestLicense={modules.requestLicense}
          />
        )}
      </div>
    </section>
  );
}
