import { Check, X } from "lucide-react";
import { StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { LicenseStatusResponse } from "../../lib/api";

export function LicenseBanner({ license }: { license: LicenseStatusResponse | null }) {
  const { t } = useLocale();
  const statusLabel = license ? licenseStatusLabel(license.status, t) : t("licenseUnknown");
  const licenseType = license ? license.license_type.toUpperCase() : "BASIC";
  return (
    <section className="panel license-banner">
      <div className="shield">{license?.status === "active" ? <Check size={28} /> : <X size={28} />}</div>
      <div>
        <span>{t("licenseStatus")}</span>
        <h2>
          {statusLabel} <StatusBadge status={licenseType} label={licenseTypeLabel(licenseType, t)} />
        </h2>
      </div>
      <div className="customer">
        <span>{t("licenseCustomer")}</span>
        <strong>{license?.customer_name ?? t("licenseUnavailable")}</strong>
      </div>
    </section>
  );
}

function licenseStatusLabel(status: string, t: (key: string) => string) {
  if (status === "active") {
    return t("licenseStatusActive");
  }
  if (status === "expired") {
    return t("licenseStatusExpired");
  }
  if (status === "inactive") {
    return t("licenseStatusInactive");
  }
  if (status === "invalid") {
    return t("licenseStatusInvalid");
  }
  return status.toUpperCase();
}

function licenseTypeLabel(type: string, t: (key: string) => string) {
  if (type === "BASIC") {
    return t("licenseTypeBasic");
  }
  if (type === "ENTERPRISE") {
    return t("licenseTypeEnterprise");
  }
  if (type === "TRIAL") {
    return t("licenseTypeTrial");
  }
  return type;
}
