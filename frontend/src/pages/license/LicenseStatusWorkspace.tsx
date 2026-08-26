import { PageTabs } from "../../components/app-ui";
import type { Locale } from "../../i18n";
import { useLocale } from "../../i18n-context";
import type { AuthorizedFeature, AuthorizedModule, LicenseStatusResponse } from "../../lib/api";
import { LicenseBanner } from "./LicenseBanner";
import { LicenseMetrics } from "./LicenseMetrics";
import { LicenseReadinessPanel } from "./LicenseReadinessPanel";
import type { LicenseStatusTab } from "./licenseWorkspaceTypes";

export function LicenseStatusWorkspace({
  activeTab,
  features,
  license,
  locale,
  modules,
  onTabChange,
  scopeSummary,
}: {
  activeTab: LicenseStatusTab;
  features: AuthorizedFeature[];
  license: LicenseStatusResponse | null | undefined;
  locale: Locale;
  modules: AuthorizedModule[];
  onTabChange: (tab: LicenseStatusTab) => void;
  scopeSummary: {
    enabledModules: number;
    enabledFeatures: number;
    totalModules: number;
    totalFeatures: number;
  };
}) {
  const { t } = useLocale();
  const currentLicense = license ?? null;

  return (
    <div className="nested-workspace license-status-workspace">
      <PageTabs
        active={activeTab}
        onChange={onTabChange}
        tabs={[
          {
            id: "overview",
            label: t("licenseStatusTabOverview"),
            description: t("licenseStatusTabOverviewDesc"),
          },
          {
            id: "readiness",
            label: t("licenseStatusTabReadiness"),
            description: t("licenseStatusTabReadinessDesc"),
          },
        ]}
      />
      {activeTab === "overview" && (
        <>
          <LicenseBanner license={currentLicense} />
          <LicenseMetrics license={currentLicense} locale={locale} scopeSummary={scopeSummary} />
        </>
      )}
      {activeTab === "readiness" && (
        <LicenseReadinessPanel features={features} license={currentLicense} modules={modules} />
      )}
    </div>
  );
}
