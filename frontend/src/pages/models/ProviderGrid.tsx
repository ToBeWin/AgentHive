import { PlugZap, Search, X } from "lucide-react";
import { useMemo, useState } from "react";
import { ApiNotice, Button, cx, EmptyState, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { LLMConnectionTestResponse, LLMProviderResponse } from "../../lib/api";
import { formatAdapterDetail, getProviderIcon, providerStatusLabelKey } from "./modelUtils";
import { ProviderReadinessSummary, resolveProviderReadiness } from "./ProviderReadinessSummary";

interface ProviderGridProps {
  providersError: string | null;
  providersList: LLMProviderResponse[];
  providersLoading: boolean;
  refetchProviders: () => void;
  lastTestResult?: LLMConnectionTestResponse | null;
  selectedProviderKey: string | null;
  setSelectedProviderKey: (providerKey: string) => void;
  testing?: boolean;
}

export function ProviderGrid({
  providersError,
  providersList,
  providersLoading,
  refetchProviders,
  lastTestResult = null,
  selectedProviderKey,
  setSelectedProviderKey,
  testing = false,
}: ProviderGridProps) {
  const { t } = useLocale();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "configured" | "missing">("all");
  const filteredProviders = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return providersList.filter((provider) => {
      const matchesQuery =
        !normalizedQuery ||
        [provider.name, provider.provider_key, provider.base_url ?? ""]
          .join(" ")
          .toLocaleLowerCase()
          .includes(normalizedQuery);
      const configured = Boolean(provider.credential_configured);
      const matchesStatus = statusFilter === "all" || (statusFilter === "configured" ? configured : !configured);
      return matchesQuery && matchesStatus;
    });
  }, [providersList, query, statusFilter]);

  return (
    <>
      <h2 className="section-heading">{t("modelsConnectedProviders")}</h2>
      {providersError && (
        <ApiNotice
          title={t("modelsProviderApiUnavailable")}
          message={t("modelsProviderApiUnavailableDetail")}
          action={<Button onClick={refetchProviders}>{t("commonRetry")}</Button>}
        />
      )}
      <div className="collection-toolbar provider-toolbar">
        <label className="collection-search">
          <Search size={16} aria-hidden="true" />
          <span className="visually-hidden">{t("modelsProviderSearchLabel")}</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={t("modelsProviderSearchPlaceholder")}
            aria-label={t("modelsProviderSearchLabel")}
          />
          {query && (
            <button
              className="collection-search-clear"
              type="button"
              onClick={() => setQuery("")}
              aria-label={t("commonClearSearch")}
              title={t("commonClearSearch")}
            >
              <X size={14} aria-hidden="true" />
            </button>
          )}
        </label>
        <label className="collection-filter">
          <span>{t("modelsProviderFilterLabel")}</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}>
            <option value="all">{t("modelsProviderFilterAll")}</option>
            <option value="configured">{t("modelsProviderFilterConfigured")}</option>
            <option value="missing">{t("modelsProviderFilterMissing")}</option>
          </select>
        </label>
        <span className="collection-toolbar-meta">
          {t("modelsProviderResults")
            .replace("{{visible}}", String(filteredProviders.length))
            .replace("{{total}}", String(providersList.length))}
        </span>
      </div>
      <div className="provider-grid">
        {providersLoading && (
          <article className="provider-card provider-card-muted">{t("modelsLoadingProviders")}</article>
        )}
        {!providersLoading && !providersList.length && (
          <div className="provider-empty-state">
            <EmptyState
              icon={<PlugZap aria-hidden="true" />}
              message={t("modelsNoProvidersDetail")}
              title={t("modelsNoProviders")}
            />
          </div>
        )}
        {!providersLoading && providersList.length > 0 && !filteredProviders.length && (
          <div className="provider-empty-state">
            <EmptyState
              icon={<Search aria-hidden="true" />}
              message={t("modelsNoProviderMatchesDetail")}
              title={t("modelsNoProviderMatches")}
            />
          </div>
        )}
        {filteredProviders.map((provider) => {
          const Icon = getProviderIcon(provider);
          const providerTesting = testing && selectedProviderKey === provider.provider_key;
          const readiness = resolveProviderReadiness({ lastTestResult, provider, testing: providerTesting });
          const statusLabelKey = providerStatusLabelKey(provider.status, provider.credential_configured);
          const readinessLabel = t(readiness.labelKey);
          const catalogStatusLabel = statusLabelKey ? t(statusLabelKey) : readinessLabel;
          return (
            <button
              className={cx(
                "provider-card provider-button",
                selectedProviderKey === provider.provider_key && "selected",
              )}
              key={provider.provider_key}
              onClick={() => setSelectedProviderKey(provider.provider_key)}
              aria-pressed={selectedProviderKey === provider.provider_key}
              type="button"
            >
              <div className="provider-icon">
                <Icon size={26} />
              </div>
              <StatusBadge
                label={statusLabelKey ? readinessLabel : catalogStatusLabel}
                status={readiness.badgeStatus}
              />
              <h2>{provider.name}</h2>
              <code>{formatAdapterDetail(provider)}</code>
              <ProviderReadinessSummary
                compact
                lastTestResult={lastTestResult}
                provider={provider}
                testing={providerTesting}
              />
            </button>
          );
        })}
      </div>
    </>
  );
}
