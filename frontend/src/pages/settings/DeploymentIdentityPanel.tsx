import { Fingerprint, ShieldCheck } from "lucide-react";
import { StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { SystemComponentReport, SystemInfoResponse } from "../../lib/api";
import { componentStatusLabel, detailPairs } from "./settingsUtils";

export function DeploymentIdentityPanel({
  info,
  licenseIdentity,
}: {
  info: SystemInfoResponse | null;
  licenseIdentity: SystemComponentReport | null;
}) {
  const { t } = useLocale();
  const identityDetails = detailPairs(licenseIdentity?.details, t);

  return (
    <section className="panel settings-identity-panel">
      <h2>{t("settingsDeploymentIdentity")}</h2>
      <div className="settings-identity-grid">
        <div className="settings-identity-card">
          <ShieldCheck size={20} />
          <span>{t("settingsProduct")}</span>
          <strong>{info?.name ?? "AgentHive"}</strong>
          <code>{info?.edition ?? "-"}</code>
        </div>
        <div className="settings-identity-card">
          <Fingerprint size={20} />
          <span>{t("settingsLicenseIdentity")}</span>
          <strong>
            {licenseIdentity ? (
              <StatusBadge status={licenseIdentity.status} label={componentStatusLabel(licenseIdentity.status, t)} />
            ) : (
              "-"
            )}
          </strong>
          <code>{licenseIdentity?.message ?? "-"}</code>
        </div>
      </div>
      <div className="settings-detail-list">
        {identityDetails.map((pair) => (
          <div key={pair.key}>
            <span>{pair.key}</span>
            <code>{pair.value}</code>
          </div>
        ))}
        {identityDetails.length === 0 && <p>{t("settingsNoIdentityDetails")}</p>}
      </div>
    </section>
  );
}
