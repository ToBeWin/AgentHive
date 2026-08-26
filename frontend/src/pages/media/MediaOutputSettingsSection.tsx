import { useLocale } from "../../i18n-context";
import type { MediaModelCapability } from "../../lib/api";
import type { MediaJobFormState } from "./mediaUtils";

export function MediaOutputSettingsSection({
  activeModelOptions,
  canConfigureModelRoute,
  form,
  modelOptions,
  onChange,
  providerHint,
}: {
  activeModelOptions: MediaModelCapability[];
  canConfigureModelRoute: boolean;
  form: MediaJobFormState;
  modelOptions: MediaModelCapability[];
  onChange: (form: MediaJobFormState) => void;
  providerHint: string;
}) {
  const { t } = useLocale();

  return (
    <div className="media-form-section">
      {canConfigureModelRoute && (
        <label>
          {t("mediaModel")}
          <select
            value={form.modelKey}
            onChange={(event) => {
              const selected = modelOptions.find((model) => model.model_key === event.target.value);
              onChange({
                ...form,
                modelKey: event.target.value,
                routingKey: selected?.routing_key ?? form.routingKey,
              });
            }}
          >
            <option value="">{t("agentsPolicyDefaultRoute")}</option>
            {modelOptions.map((model) => (
              <option key={model.model_key} value={model.model_key} disabled={model.status !== "active"}>
                {model.display_name} · {model.model_key}
                {model.status !== "active" ? ` · ${t("mediaProviderNotConfigured")}` : ""}
              </option>
            ))}
          </select>
          {!form.modelKey && activeModelOptions.length > 0 && (
            <small className="media-form-help">
              {t("mediaDefaultRouteConfigured").replace("{{count}}", String(activeModelOptions.length))}
            </small>
          )}
        </label>
      )}
      {providerHint && <div className="form-message error">{providerHint}</div>}
      {canConfigureModelRoute && (
        <label>
          {t("mediaRoutingKey")}
          <input value={form.routingKey} onChange={(event) => onChange({ ...form, routingKey: event.target.value })} />
        </label>
      )}
      <div className="budget-form-grid">
        <label>
          {t("mediaResolution")}
          <input value={form.resolution} onChange={(event) => onChange({ ...form, resolution: event.target.value })} />
        </label>
        <label>
          {t("mediaSeed")}
          <input value={form.seed} onChange={(event) => onChange({ ...form, seed: event.target.value })} />
        </label>
      </div>
      {form.kind === "image" ? (
        <div className="budget-form-grid">
          <label>
            {t("mediaImageCount")}
            <input
              min={1}
              max={8}
              type="number"
              value={form.imageCount}
              onChange={(event) => onChange({ ...form, imageCount: Number(event.target.value) })}
            />
          </label>
          <label>
            {t("mediaAspectRatio")}
            <input
              value={form.aspectRatio}
              onChange={(event) => onChange({ ...form, aspectRatio: event.target.value })}
            />
          </label>
        </div>
      ) : (
        <div className="budget-form-grid">
          <label>
            {t("mediaDuration")}
            <input
              min={1}
              max={60}
              type="number"
              value={form.durationSeconds}
              onChange={(event) => onChange({ ...form, durationSeconds: Number(event.target.value) })}
            />
          </label>
          <label>
            {t("mediaFps")}
            <input
              min={1}
              max={120}
              type="number"
              value={form.fps}
              onChange={(event) => onChange({ ...form, fps: Number(event.target.value) })}
            />
          </label>
        </div>
      )}
    </div>
  );
}
