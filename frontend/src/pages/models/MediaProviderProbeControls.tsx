import { RadioTower } from "lucide-react";
import { Button } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { CredentialFormState } from "./modelUtils";

interface MediaProviderProbeControlsProps {
  canWrite: boolean;
  credentialForm: CredentialFormState;
  onLiveProbe: () => void;
  setCredentialForm: React.Dispatch<React.SetStateAction<CredentialFormState>>;
  testing: boolean;
}

export function MediaProviderProbeControls({
  canWrite,
  credentialForm,
  onLiveProbe,
  setCredentialForm,
  testing,
}: MediaProviderProbeControlsProps) {
  const { t } = useLocale();

  return (
    <div className="media-live-probe">
      <div>
        <strong>{t("modelsMediaLiveProbe")}</strong>
        <span>{t("modelsMediaLiveProbeHelp")}</span>
      </div>
      <label>
        {t("modelsProbePath")}
        <input
          disabled={!canWrite}
          placeholder="/models"
          value={credentialForm.probePath}
          onChange={(event) => {
            setCredentialForm((current) => ({ ...current, probePath: event.target.value }));
          }}
        />
      </label>
      <Button onClick={onLiveProbe} disabled={!canWrite || testing}>
        <RadioTower size={16} /> {testing ? t("modelsTesting") : t("modelsRunLiveProbe")}
      </Button>
    </div>
  );
}
