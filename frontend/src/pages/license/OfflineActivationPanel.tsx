import { Copy, Download, FileUp, Upload } from "lucide-react";
import type { ChangeEvent, Dispatch, SetStateAction } from "react";
import { useRef, useState } from "react";
import { ApiNotice, Button } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { ActivationRequestResponse } from "../../lib/api";

type LicenseActionState = {
  activating: boolean;
  error: string | null;
  exporting: boolean;
  message: string | null;
};

export function OfflineActivationPanel({
  actions,
  activationRequest,
  canWriteLicense,
  licensePayload,
  localError,
  localNotice,
  onActivate,
  onDownloadRequest,
  setLicensePayload,
}: {
  actions: LicenseActionState;
  activationRequest: ActivationRequestResponse | null;
  canWriteLicense: boolean;
  licensePayload: string;
  localError: string | null;
  localNotice: string | null;
  onActivate: () => void;
  onDownloadRequest: () => void;
  setLicensePayload: Dispatch<SetStateAction<string>>;
}) {
  const { t } = useLocale();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [fileNotice, setFileNotice] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const canActivate = canWriteLicense && licensePayload.trim().length > 0 && !actions.activating;
  const copyRequestCode = async () => {
    if (activationRequest?.request_code) {
      await navigator.clipboard?.writeText(activationRequest.request_code);
    }
  };

  const importLicenseFile = async (event: ChangeEvent<HTMLInputElement>) => {
    setFileNotice(null);
    setFileError(null);
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) {
      return;
    }
    if (file.size > 256 * 1024) {
      setFileError(t("licenseImportFileTooLarge"));
      return;
    }
    try {
      const content = await file.text();
      const trimmed = content.trim();
      if (!trimmed) {
        setFileError(t("licenseImportFileEmpty"));
        return;
      }
      setLicensePayload(trimmed);
      setFileNotice(t("licenseImportedFile").replace("{{fileName}}", file.name));
    } catch {
      setFileError(t("licenseImportFileFailed"));
    }
  };

  return (
    <section className="panel license-activation-panel">
      <h2>
        {t("licenseOfflineActivation")} <span>{t("licenseOfflineActivationAlt")}</span>
      </h2>
      <p>{t("licenseOfflineHelp")}</p>
      {(localNotice || actions.message) && (
        <ApiNotice title={t("licenseActionComplete")} message={localNotice ?? actions.message ?? ""} />
      )}
      {(localError || actions.error) && (
        <ApiNotice title={t("licenseActionFailed")} message={localError ?? actions.error ?? ""} />
      )}
      {(fileNotice || fileError) && (
        <ApiNotice
          title={fileError ? t("licenseActionFailed") : t("licenseActionComplete")}
          message={fileError ?? fileNotice ?? ""}
        />
      )}
      {!canWriteLicense && (
        <ApiNotice title={t("licenseWritePermissionTitle")} message={t("licenseWritePermissionMessage")} />
      )}
      <div className="license-actions">
        <Button onClick={onDownloadRequest} disabled={actions.exporting}>
          <Download size={16} /> {actions.exporting ? t("licenseExporting") : t("licenseExportRequest")}
        </Button>
        <Button onClick={() => fileInputRef.current?.click()} disabled={!canWriteLicense}>
          <Upload size={16} /> {t("licenseImportFile")}
        </Button>
        <input
          ref={fileInputRef}
          accept=".json,.license,.txt,application/json,text/plain"
          className="visually-hidden-file"
          type="file"
          onChange={(event) => void importLicenseFile(event)}
        />
      </div>
      {activationRequest ? (
        <div className="activation-request-card">
          <div>
            <span>{t("licenseActivationRequestId")}</span>
            <strong>{activationRequest.request_id}</strong>
          </div>
          <div>
            <span>{t("licenseActivationRequestHash")}</span>
            <code>{shortHash(activationRequest.request_hash)}</code>
          </div>
          <button type="button" onClick={() => void copyRequestCode()}>
            <Copy size={15} /> {t("licenseCopyRequestCode")}
          </button>
        </div>
      ) : null}
      <label className="field-block license-import">
        <span>{t("licenseSignedJson")}</span>
        <textarea
          disabled={!canWriteLicense}
          placeholder={t("licenseSignedJsonPlaceholder")}
          value={licensePayload}
          onChange={(event) => setLicensePayload(event.target.value)}
        />
      </label>
      <Button variant="primary" onClick={onActivate} disabled={!canActivate}>
        <FileUp size={16} /> {actions.activating ? t("licenseActivating") : t("licenseImportActivate")}
      </Button>
    </section>
  );
}

function shortHash(hash: string): string {
  if (hash.length <= 18) {
    return hash;
  }
  return `${hash.slice(0, 10)}...${hash.slice(-8)}`;
}
