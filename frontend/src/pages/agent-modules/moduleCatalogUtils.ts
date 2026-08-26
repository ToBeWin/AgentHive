import {
  BarChart3,
  Boxes,
  FileText,
  Headset,
  ImagePlus,
  Landmark,
  type LucideIcon,
  Megaphone,
  NotebookText,
  PenLine,
  Video,
} from "lucide-react";
import type { AgentModuleCatalogEntry, AgentModuleState } from "../../lib/api";

export type LicenseFilter = "all" | "licensed" | "requires_upgrade";
export type StateFilter = "all" | AgentModuleState;

const moduleIconMap: Record<string, LucideIcon> = {
  "agent.customer_service": Headset,
  "agent.hr_screening": NotebookText,
  "agent.copywriting": Megaphone,
  "agent.image_generation": ImagePlus,
  "agent.video_generation": Video,
  "agent.content_analysis": BarChart3,
  "agent.report_writer": FileText,
  "agent.product_design": PenLine,
  "agent.finance": Landmark,
  "agent.store_operations": Headset,
  "agent.data_analyst": BarChart3,
};

export function filterModules(
  modules: AgentModuleCatalogEntry[],
  {
    category,
    licenseFilter,
    query,
    stateFilter,
  }: {
    category: string;
    licenseFilter: LicenseFilter;
    query: string;
    stateFilter: StateFilter;
  },
) {
  const needle = query.trim().toLowerCase();
  return modules.filter((module) => {
    if (category !== "All Modules" && moduleCategory(module) !== category) {
      return false;
    }
    if (licenseFilter === "licensed" && !module.licensed) {
      return false;
    }
    if (
      licenseFilter === "requires_upgrade" &&
      module.licensed &&
      !module.missing_features?.length &&
      !module.missing_dependencies?.length
    ) {
      return false;
    }
    if (stateFilter !== "all" && module.state !== stateFilter) {
      return false;
    }
    if (!needle) {
      return true;
    }
    return [module.name, module.description, module.scenario, module.priority, module.id].some((value) =>
      String(value ?? "")
        .toLowerCase()
        .includes(needle),
    );
  });
}

export function moduleCategories(modules: AgentModuleCatalogEntry[]) {
  return ["All Modules", ...Array.from(new Set(modules.map(moduleCategory))).sort()];
}

export function moduleStates(modules: AgentModuleCatalogEntry[]): StateFilter[] {
  return ["all", ...Array.from(new Set(modules.map((module) => module.state))).sort()];
}

export function getModuleIcon(module: AgentModuleCatalogEntry) {
  return moduleIconMap[module.id] ?? Boxes;
}

export function formatState(state: AgentModuleState | string) {
  return state.replace(/_/g, " ").toUpperCase();
}

export function formatModuleState(state: AgentModuleState | string, t: (key: string) => string) {
  switch (state) {
    case "not_installed":
      return t("modulesStateNotInstalled");
    case "installed":
      return t("modulesStateInstalled");
    case "enabled":
      return t("modulesStateEnabled");
    case "disabled":
      return t("modulesStateDisabled");
    case "expired":
      return t("modulesStateExpired");
    case "not_licensed":
      return t("modulesStateNotLicensed");
    default:
      return formatState(state);
  }
}

export function formatCategory(category: string, t: (key: string) => string) {
  switch (category) {
    case "All Modules":
      return t("modulesAllModules");
    case "Customer Support":
      return t("modulesCategoryCustomerSupport");
    case "Human Resources":
      return t("modulesCategoryHumanResources");
    case "Marketing":
      return t("modulesCategoryMarketing");
    case "Finance":
      return t("modulesCategoryFinance");
    case "Operations":
      return t("modulesCategoryOperations");
    default:
      return t("modulesCategoryOther");
  }
}

function moduleCategory(module: AgentModuleCatalogEntry) {
  const scenario = String(module.scenario ?? "").toLowerCase();
  if (scenario.includes("support") || scenario.includes("customer")) {
    return "Customer Support";
  }
  if (scenario.includes("resume") || scenario.includes("hr") || scenario.includes("human")) {
    return "Human Resources";
  }
  if (
    scenario.includes("copy") ||
    scenario.includes("content") ||
    scenario.includes("marketing") ||
    scenario.includes("image") ||
    scenario.includes("video")
  ) {
    return "Marketing";
  }
  if (scenario.includes("finance") || scenario.includes("invoice") || scenario.includes("expense")) {
    return "Finance";
  }
  if (scenario.includes("report") || scenario.includes("operation") || scenario.includes("data")) {
    return "Operations";
  }
  return "Other";
}
