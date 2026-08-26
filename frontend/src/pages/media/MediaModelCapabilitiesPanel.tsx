import { Boxes, ImagePlus, Video } from "lucide-react";
import { ApiNotice, Button, LoadingState, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { MediaModelCapability } from "../../lib/api";
import { formatCurrency } from "../../lib/formatters";
import { kindLabelKey } from "./mediaUtils";

export function MediaModelCapabilitiesPanel({
  error,
  loading,
  models,
  onRetry,
}: {
  error: string | null;
  loading: boolean;
  models: MediaModelCapability[];
  onRetry: () => void;
}) {
  const { t } = useLocale();
  return (
    <section className="panel media-model-panel">
      <div className="panel-title-row">
        <div>
          <h2>{t("mediaModelsTitle")}</h2>
          <p>{t("mediaModelsSubtitle")}</p>
        </div>
      </div>
      {error && (
        <ApiNotice
          title={t("mediaModelsUnavailable")}
          message={error}
          action={<Button onClick={onRetry}>{t("commonRetry")}</Button>}
        />
      )}
      {loading && <LoadingState lines={3} />}
      <div className="media-model-grid">
        {models.map((model) => {
          const Icon = model.kind === "video" ? Video : ImagePlus;
          const configurationIssues = model.configuration_issues.join(", ");
          return (
            <article className="media-model-card" key={`${model.provider_key}:${model.model_key}`}>
              <span className="media-model-icon">
                <Icon size={18} />
              </span>
              <div>
                <strong>{model.display_name}</strong>
                <span className="media-model-key">{model.model_key}</span>
              </div>
              <div className="media-model-badges">
                <StatusBadge label={t(kindLabelKey(model.kind))} status={model.kind} />
                <StatusBadge
                  label={t(model.status === "active" ? "mediaProviderActive" : "mediaProviderNotConfigured")}
                  status={model.status}
                />
              </div>
              <span className="media-model-price">
                {formatCurrency(model.price_usd)} /{" "}
                {t(model.price_unit === "second" ? "mediaPriceSecond" : "mediaPriceOutput")}
              </span>
              <small>{model.capabilities.join(" · ")}</small>
              {configurationIssues && (
                <small className="media-model-config-hint">
                  {t("mediaProviderMissingConfig").replace("{{items}}", configurationIssues)}
                </small>
              )}
            </article>
          );
        })}
        {!loading && !models.length && (
          <div className="media-empty-inline">
            <Boxes size={18} />
            <span>{t("mediaModelsUnavailable")}</span>
          </div>
        )}
      </div>
    </section>
  );
}
