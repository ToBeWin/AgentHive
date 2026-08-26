import type React from "react";
import { useLocale } from "../../i18n-context";
import type { LicenseFilter, StateFilter } from "./moduleCatalogUtils";
import { formatCategory, formatModuleState } from "./moduleCatalogUtils";

export function ModuleFilters({
  categories,
  category,
  licenseFilter,
  setCategory,
  setLicenseFilter,
  setStateFilter,
  stateFilter,
  stateOptions,
}: {
  categories: string[];
  category: string;
  licenseFilter: LicenseFilter;
  setCategory: (category: string) => void;
  setLicenseFilter: (filter: LicenseFilter) => void;
  setStateFilter: (filter: StateFilter) => void;
  stateFilter: StateFilter;
  stateOptions: StateFilter[];
}) {
  const { t } = useLocale();
  const activeFilters = [
    category !== "All Modules" ? formatCategory(category, t) : "",
    licenseFilter !== "all" ? formatLicenseFilter(licenseFilter, t) : "",
    stateFilter !== "all" ? formatModuleState(stateFilter, t) : "",
  ].filter(Boolean);
  const summary = activeFilters.length ? activeFilters.join(" / ") : t("modulesFilterNoActive");

  return (
    <aside className="filters module-filters">
      <details className="module-filter-details" open={activeFilters.length > 0}>
        <summary>
          <span>
            <strong>{t("modulesFilterPanelTitle")}</strong>
            <small>{summary}</small>
          </span>
          <em>{t("modulesFilterActiveCount").replace("{{count}}", String(activeFilters.length))}</em>
        </summary>
        <FilterGroup title={t("modulesCategories")}>
          {categories.map((item) => (
            <label key={item}>
              <input
                checked={category === item}
                name="module-category"
                type="radio"
                onChange={() => setCategory(item)}
              />{" "}
              {formatCategory(item, t)}
            </label>
          ))}
        </FilterGroup>
        <FilterGroup title={t("modulesLicenseStatus")}>
          {[
            { label: t("modulesAllLicenseStates"), value: "all" },
            { label: t("modulesLicensed"), value: "licensed" },
            { label: t("modulesRequiresUpgrade"), value: "requires_upgrade" },
          ].map((item) => (
            <label key={item.value}>
              <input
                checked={licenseFilter === item.value}
                name="module-license"
                type="radio"
                onChange={() => setLicenseFilter(item.value as LicenseFilter)}
              />{" "}
              {item.label}
            </label>
          ))}
        </FilterGroup>
        <FilterGroup title={t("modulesRuntimeState")}>
          {stateOptions.map((state) => (
            <label key={state}>
              <input
                checked={stateFilter === state}
                name="module-state"
                type="radio"
                onChange={() => setStateFilter(state)}
              />{" "}
              {state === "all" ? t("modulesAllStates") : formatModuleState(state, t)}
            </label>
          ))}
        </FilterGroup>
      </details>
    </aside>
  );
}

function FilterGroup({ children, title }: { children: React.ReactNode; title: string }) {
  return (
    <div className="filter-group">
      <h3>{title}</h3>
      {children}
    </div>
  );
}

function formatLicenseFilter(filter: LicenseFilter, t: (key: string) => string) {
  switch (filter) {
    case "licensed":
      return t("modulesLicensed");
    case "requires_upgrade":
      return t("modulesRequiresUpgrade");
    default:
      return t("modulesAllLicenseStates");
  }
}
