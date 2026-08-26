import { useLocale } from "../../i18n-context";
import type { MediaAssetKind } from "../../lib/api";
import type { MediaJobFormState } from "./mediaUtils";

export function MediaAssetsSection({
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
          {t("mediaReferenceUrl")}
          <input
            type="url"
            placeholder={t("mediaReferenceUrlPlaceholder")}
            value={form.referenceUrl}
            onChange={(event) => onChange({ ...form, referenceUrl: event.target.value })}
          />
        </label>
        <label>
          {t("mediaReferenceKind")}
          <select
            value={form.referenceKind}
            onChange={(event) => onChange({ ...form, referenceKind: event.target.value as MediaAssetKind })}
          >
            <option value="image">{t("mediaReferenceKindImage")}</option>
            <option value="video">{t("mediaReferenceKindVideo")}</option>
          </select>
          <small className="media-form-help">{t("mediaReferenceUrlHelp")}</small>
        </label>
      </div>
    </div>
  );
}
