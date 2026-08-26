import { PlugZap } from "lucide-react";
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
        {providersList.map((provider) => {
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
