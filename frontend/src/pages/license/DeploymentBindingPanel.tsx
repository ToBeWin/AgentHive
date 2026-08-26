import { Copy, Fingerprint } from "lucide-react";
import { useState } from "react";
import { cx } from "../../components/app-ui";
import type { Locale } from "../../i18n";
import { useLocale } from "../../i18n-context";
import type { LicenseStatusResponse } from "../../lib/api";
import { formatDate, shortFingerprint } from "./licenseUtils";

export function DeploymentBindingPanel({ license, locale }: { license: LicenseStatusResponse | null; locale: Locale }) {
  const { t } = useLocale();
  return (
    <section className="panel">
      <h2>
        {t("licenseDeploymentBinding")} <span>{t("licenseDeploymentBindingAlt")}</span>
      </h2>
      <div className="license-binding-grid">
        <LicenseField
          label={t("licenseDeploymentId")}
          value={license?.deployment_id ?? t("licenseNotAvailable")}
          copyable
        />
        <LicenseField
          label={t("licenseRuntimeDeploymentId")}
          value={license?.runtime_deployment_id ?? t("licenseNotAvailable")}
          tone={bindingTone(license?.deployment_id, license?.runtime_deployment_id)}
          copyable
        />
        <LicenseField label={t("licenseInstallId")} value={license?.install_id ?? t("licenseNotAvailable")} copyable />
        <LicenseField
          label={t("licenseRuntimeInstallId")}
          value={license?.runtime_install_id ?? t("licenseNotAvailable")}
          tone={bindingTone(license?.install_id, license?.runtime_install_id)}
          copyable
        />
        <LicenseField
          label={t("licenseMachineFingerprint")}
          value={license ? shortFingerprint(license.machine_fingerprint_hash) : t("licenseNotAvailable")}
          tone={bindingTone(license?.machine_fingerprint_hash, license?.runtime_machine_fingerprint_hash)}
        />
        <LicenseField
          label={t("licenseRuntimeMachineFingerprint")}
          value={
            license?.runtime_machine_fingerprint_hash
              ? shortFingerprint(license.runtime_machine_fingerprint_hash)
              : t("licenseNotAvailable")
          }
          tone={bindingTone(license?.machine_fingerprint_hash, license?.runtime_machine_fingerprint_hash)}
        />
        <LicenseField
          label={t("licenseActivatedAt")}
          value={formatDate(license?.activated_at ?? null, locale, t("licenseNotSet"))}
        />
      </div>
      {Boolean(license?.verification_issues.length) && (
        <div className="license-issues">
          <strong>{t("licenseVerificationIssues")}</strong>
          <ul>
            {license?.verification_issues.map((issue) => (
              <li key={issue}>{licenseIssueLabel(issue, t)}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="inline-note">{t("licenseBindingNote")}</div>
    </section>
  );
}

function bindingTone(left?: string | null, right?: string | null) {
  if (!left || !right) {
    return undefined;
  }
  return left === right ? "good" : "bad";
}

function licenseIssueLabel(issue: string, t: (key: string) => string) {
  const labels: Record<string, string> = {
    deployment_id_mismatch: t("licenseIssueDeploymentMismatch"),
    install_id_mismatch: t("licenseIssueInstallMismatch"),
    license_expired: t("licenseIssueExpired"),
    machine_fingerprint_mismatch: t("licenseIssueFingerprintMismatch"),
    no_active_license: t("licenseIssueNoActiveLicense"),
  };
  return labels[issue] ?? issue;
}

function LicenseField({
  copyable = false,
  label,
  tone,
  value,
}: {
  copyable?: boolean;
  label: string;
  tone?: "good" | "bad";
  value: string;
}) {
  const { t } = useLocale();
  const [copied, setCopied] = useState(false);
  const copyValue = async () => {
    if (await writeClipboardText(value)) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2400);
    }
  };
  return (
    <div className="field-block">
      <span>{label}</span>
      <div className={cx("copy-field", tone)}>
        <code>{value}</code>
        {copyable ? (
          <button
            aria-label={`${t("licenseCopyLabel")} ${label}`}
            className="copy-button"
            type="button"
            onClick={() => void copyValue()}
            title={copied ? t("licenseCopied") : `${t("licenseCopyLabel")} ${label}`}
          >
            <Copy size={16} />
          </button>
        ) : (
          <Fingerprint size={16} />
        )}
      </div>
      {copied && <small className="copy-feedback">{t("licenseCopied")}</small>}
    </div>
  );
}

async function writeClipboardText(value: string) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value);
      return true;
    }
  } catch {
    // Fall back to the legacy copy path below when browser permissions block navigator.clipboard.
  }

  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  return copied;
}
