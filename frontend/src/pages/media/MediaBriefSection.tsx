import { useLocale } from "../../i18n-context";
import type { MediaGenerationKind, MediaGenerationMode } from "../../lib/api";
import { defaultRoutingKeyForKind, type MediaJobFormState } from "./mediaUtils";

export function MediaBriefSection({
  form,
  onChange,
}: {
  form: MediaJobFormState;
  onChange: (form: MediaJobFormState) => void;
}) {
  const { t } = useLocale();

  return (
    <div className="media-form-section">
      <div className="budget-form-grid">
        <label>
          {t("mediaKind")}
          <select
            value={form.kind}
            onChange={(event) =>
              onChange({
                ...form,
                kind: event.target.value as MediaGenerationKind,
                modelKey: "",
                routingKey: defaultRoutingKeyForKind(event.target.value as MediaGenerationKind),
              })
            }
          >
            <option value="image">{t("mediaKindImage")}</option>
            <option value="video">{t("mediaKindVideo")}</option>
          </select>
        </label>
        <label>
          {t("mediaMode")}
          <select
            value={form.mode}
            onChange={(event) => onChange({ ...form, mode: event.target.value as MediaGenerationMode })}
          >
            <option value="manual_prompt">{t("mediaModeManualPrompt")}</option>
            <option value="natural_language">{t("mediaModeNaturalLanguage")}</option>
            <option value="material_breakdown">{t("mediaModeMaterialBreakdown")}</option>
          </select>
        </label>
      </div>
      <label>
        {t("mediaPrompt")}
        <textarea
          placeholder={t("mediaPromptPlaceholder")}
          rows={5}
          value={form.prompt}
          onChange={(event) => onChange({ ...form, prompt: event.target.value })}
        />
      </label>
      <label>
        {t("mediaNegativePrompt")}
        <textarea
          placeholder={t("mediaNegativePromptPlaceholder")}
          rows={2}
          value={form.negativePrompt}
          onChange={(event) => onChange({ ...form, negativePrompt: event.target.value })}
        />
      </label>
    </div>
  );
}
