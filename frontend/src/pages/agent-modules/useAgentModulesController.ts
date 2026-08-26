import { useMemo, useState } from "react";
import type { PageId } from "../../data";
import { useAgentModuleActions, useAgentModules } from "../../hooks/useAdminData";
import { useLocale } from "../../i18n-context";
import type { AgentModuleCatalogEntry } from "../../lib/api";
import {
  filterModules,
  type LicenseFilter,
  moduleCategories,
  moduleStates,
  type StateFilter,
} from "./moduleCatalogUtils";

type ModuleView = "all" | "enabled" | "available" | "needs_action";
type ModuleWorkspace = "catalog" | "details";

const AGENT_TAB_REQUEST_KEY = "agenthive.agents.default_tab";
const AGENT_KEY_REQUEST_KEY = "agenthive.agents.default_agent_key";
const LICENSE_TAB_REQUEST_KEY = "agenthive.license.default_tab";

export function useAgentModulesController({
  isPrototype = false,
  onNavigate,
}: {
  isPrototype?: boolean;
  onNavigate?: (page: PageId) => void;
}) {
  const { t } = useLocale();
  const { data: modules, error, loading, refetch } = useAgentModules({ fallbackOnError: isPrototype });
  const actions = useAgentModuleActions({ fallbackOnError: isPrototype });
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All Modules");
  const [licenseFilter, setLicenseFilter] = useState<LicenseFilter>("all");
  const [stateFilter, setStateFilter] = useState<StateFilter>("all");
  const [moduleView, setModuleView] = useState<ModuleView>("all");
  const [moduleWorkspace, setModuleWorkspace] = useState<ModuleWorkspace>("catalog");
  const [selectedModuleId, setSelectedModuleId] = useState("");
  const [localNotice, setLocalNotice] = useState("");

  const catalog = modules ?? [];
  const categories = useMemo(() => moduleCategories(catalog), [catalog]);
  const stateOptions = useMemo(() => moduleStates(catalog), [catalog]);
  const moduleViewCounts = useMemo(
    () => ({
      all: catalog.length,
      available: catalog.filter((module) => moduleMatchesView(module, "available")).length,
      enabled: catalog.filter((module) => moduleMatchesView(module, "enabled")).length,
      needs_action: catalog.filter((module) => moduleMatchesView(module, "needs_action")).length,
    }),
    [catalog],
  );
  const modulesInView = useMemo(
    () => catalog.filter((module) => moduleMatchesView(module, moduleView)),
    [catalog, moduleView],
  );
  const visibleModules = useMemo(
    () => filterModules(modulesInView, { category, licenseFilter, query, stateFilter }),
    [category, licenseFilter, modulesInView, query, stateFilter],
  );
  const selectedModule = useMemo(
    () =>
      catalog.find((module) => module.id === selectedModuleId) ??
      visibleModules.find((module) => module.id === selectedModuleId) ??
      visibleModules[0] ??
      null,
    [catalog, selectedModuleId, visibleModules],
  );

  const runModuleAction = async (moduleId: string, action: "install" | "enable" | "disable") => {
    const response =
      action === "install"
        ? await actions.installModule(moduleId)
        : action === "enable"
          ? await actions.enableModule(moduleId)
          : await actions.disableModule(moduleId);
    if (response) {
      await refetch();
    }
  };

  const flashNotice = (message: string) => {
    setLocalNotice(message);
    window.setTimeout(() => setLocalNotice(""), 2600);
  };

  const moduleName = (moduleId: string) => catalog.find((item) => item.id === moduleId)?.name ?? moduleId;
  const selectModule = (moduleId: string) => {
    setSelectedModuleId(moduleId);
    setModuleWorkspace("details");
  };
  const openAgentConfiguration = (moduleId: string) => {
    window.sessionStorage.setItem(AGENT_TAB_REQUEST_KEY, "instances");
    window.sessionStorage.setItem(AGENT_KEY_REQUEST_KEY, moduleId.replace(/^agent\./, ""));
    flashNotice(t("modulesConfigureNotice").replace("{{name}}", moduleName(moduleId)));
    onNavigate?.("agents");
  };
  const requestLicense = (moduleId: string) => {
    window.sessionStorage.setItem(LICENSE_TAB_REQUEST_KEY, "scope");
    flashNotice(t("modulesRequestLicenseNotice").replace("{{name}}", moduleName(moduleId)));
    onNavigate?.("license");
  };

  return {
    actions,
    catalog,
    categories,
    category,
    error,
    licenseFilter,
    loading,
    localNotice,
    moduleView,
    moduleViewCounts,
    moduleWorkspace,
    openAgentConfiguration,
    query,
    refetch,
    requestLicense,
    runModuleAction,
    selectedModule,
    selectModule,
    setCategory,
    setLicenseFilter,
    setModuleView,
    setModuleWorkspace,
    setQuery,
    setStateFilter,
    stateFilter,
    stateOptions,
    visibleModules,
  };
}

function moduleMatchesView(module: AgentModuleCatalogEntry, view: ModuleView) {
  switch (view) {
    case "enabled":
      return module.enabled || module.state === "enabled";
    case "available":
      return module.licensed && module.state !== "enabled" && module.state !== "expired";
    case "needs_action":
      return (
        !module.licensed ||
        module.state === "expired" ||
        module.state === "not_licensed" ||
        Boolean(module.missing_features?.length) ||
        Boolean(module.missing_dependencies?.length)
      );
    default:
      return true;
  }
}
