import type { Locale } from "../../i18n";
import { useLocale } from "../../i18n-context";
import type { LicenseStatusResponse } from "../../lib/api";
import type { LicenseScopeSummary } from "./licenseUtils";
import { formatDate } from "./licenseUtils";

export function LicenseMetrics({
  license,
  locale,
  scopeSummary,
}: {
  license: LicenseStatusResponse | null;
  locale: Locale;
  scopeSummary: LicenseScopeSummary;
}) {
  const { t } = useLocale();
  return (
    <div className="license-status-grid">
      <StatusMetric
        label={t("licenseModules")}
        value={`${scopeSummary.enabledModules}/${scopeSummary.totalModules}`}
        detail={t("licenseEnabledDetail")}
      />
      <StatusMetric
        label={t("licenseFeatures")}
        value={`${scopeSummary.enabledFeatures}/${scopeSummary.totalFeatures}`}
        detail={t("licenseIncludedDetail")}
      />
      <StatusMetric
        label={t("licenseMaxUsers")}
        value={formatLimit(license?.max_users ?? null, t("licenseUnlimited"))}
        detail={t("licenseUserCapacity")}
      />
      <StatusMetric
        label={t("licenseMaxAgents")}
        value={formatLimit(license?.max_agents ?? null, t("licenseUnlimited"))}
        detail={t("licenseAgentCapacity")}
      />
      <StatusMetric
        label={t("licenseMaxKnowledge")}
        value={formatStorageLimit(license?.max_kb_size_gb ?? null, t("licenseUnlimited"))}
        detail={t("licenseKnowledgeCapacity")}
      />
      <StatusMetric
        label={t("licenseMaintenance")}
        value={formatDate(license?.maintenance_until ?? null, locale, t("licenseNotSet"))}
        detail={t("licenseUpgradeWindow")}
      />
      <StatusMetric
        label={t("licenseExpires")}
        value={formatDate(license?.expires_at ?? null, locale, t("licenseNotSet"))}
        detail={t("licenseCurrentVersion")}
      />
    </div>
  );
}

function formatLimit(value: number | null, fallback: string) {
  return value === null ? fallback : value.toLocaleString();
}

function formatStorageLimit(value: number | string | null, fallback: string) {
  if (value === null) {
    return fallback;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return `${parsed.toLocaleString(undefined, { maximumFractionDigits: 2 })} GiB`;
}

function StatusMetric({ detail, label, value }: { detail: string; label: string; value: string }) {
  return (
    <section className="panel license-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </section>
  );
}
