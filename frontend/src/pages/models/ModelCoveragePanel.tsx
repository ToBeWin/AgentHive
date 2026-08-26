import { Check } from "lucide-react";
import { useLocale } from "../../i18n-context";
import type { LLMProviderResponse } from "../../lib/api";
import {
  getConfiguredProviderKeys,
  modelCoverageGroups,
  modelProtocolCoverage,
  providerDisplayNames,
} from "./modelUtils";

interface ModelCoveragePanelProps {
  providersList: LLMProviderResponse[];
}

export function ModelCoveragePanel({ providersList }: ModelCoveragePanelProps) {
  const { t } = useLocale();
  const configuredProviderKeys = getConfiguredProviderKeys(providersList);

  return (
    <section className="panel model-coverage-panel">
      <div className="panel-heading">
        <div>
          <h2>{t("modelsProviderCoverage")}</h2>
          <p>{t("modelsCoverageSubtitle")}</p>
        </div>
        <span className="coverage-note">{t("modelsCoverageLiteLlmNote")}</span>
      </div>
      <div className="model-protocol-grid">
        {modelProtocolCoverage.map((protocol) => {
          const configuredCount = protocol.providerKeys.filter((key) => configuredProviderKeys.has(key)).length;
          const configured = configuredCount > 0;
          return (
            <article
              className={configured ? "protocol-coverage-card configured" : "protocol-coverage-card"}
              key={protocol.key}
            >
              <span>{t(`modelsProtocol${capitalizeGroupKey(protocol.key)}`)}</span>
              <strong>{configured ? t("modelsProtocolReady") : t("modelsProtocolReadyViaCatalog")}</strong>
              <small>
                {t(`modelsProtocol${capitalizeGroupKey(protocol.key)}Detail`).replace(
                  "{{count}}",
                  String(configuredCount),
                )}
              </small>
            </article>
          );
        })}
      </div>
      <div className="model-coverage-grid">
        {modelCoverageGroups.map((group) => {
          const configuredCount = group.providerKeys.filter((key) => configuredProviderKeys.has(key)).length;
          return (
            <article className="coverage-group-card" key={group.key}>
              <div className="coverage-group-header">
                <h3>{t(`modelsCoverage${capitalizeGroupKey(group.key)}`)}</h3>
                <span>
                  {configuredCount}/{group.providerKeys.length} {t("modelsCoverageConfigured")}
                </span>
              </div>
              <div className="coverage-provider-list">
                {group.providerKeys.map((providerKey) => {
                  const configured = configuredProviderKeys.has(providerKey);
                  return (
                    <span className={configured ? "configured" : undefined} key={providerKey}>
                      {configured && <Check size={12} />}
                      {providerDisplayNames[providerKey] ?? providerKey}
                    </span>
                  );
                })}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function capitalizeGroupKey(groupKey: string) {
  return groupKey.charAt(0).toUpperCase() + groupKey.slice(1);
}
