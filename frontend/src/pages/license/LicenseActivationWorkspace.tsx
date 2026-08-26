import type { Dispatch, SetStateAction } from "react";
import { PageTabs } from "../../components/app-ui";
import type { useLicenseActivationActions } from "../../hooks/useAdminData";
import type { Locale } from "../../i18n";
import { useLocale } from "../../i18n-context";
import type { ActivationRequestResponse, LicenseStatusResponse } from "../../lib/api";
import { DeploymentBindingPanel } from "./DeploymentBindingPanel";
import type { LicenseActivationTab } from "./licenseWorkspaceTypes";
import { OfflineActivationPanel } from "./OfflineActivationPanel";

export function LicenseActivationWorkspace({
  activationRequest,
  activeTab,
  actions,
  canWriteLicense,
  license,
  licensePayload,
  locale,
  localError,
  localNotice,
  onActivate,
  onDownloadRequest,
  onTabChange,
  setLicensePayload,
}: {
  activationRequest: ActivationRequestResponse | null;
  activeTab: LicenseActivationTab;
  actions: ReturnType<typeof useLicenseActivationActions>;
  canWriteLicense: boolean;
  license: LicenseStatusResponse | null | undefined;
  licensePayload: string;
  locale: Locale;
  localError: string | null;
  localNotice: string | null;
  onActivate: () => void;
  onDownloadRequest: () => void;
  onTabChange: (tab: LicenseActivationTab) => void;
  setLicensePayload: Dispatch<SetStateAction<string>>;
}) {
  const { t } = useLocale();
  const currentLicense = license ?? null;

  return (
    <div className="nested-workspace">
      <PageTabs
        active={activeTab}
        onChange={onTabChange}
        tabs={[
          {
            id: "binding",
            label: t("licenseActivationTabBinding"),
            description: t("licenseActivationTabBindingDesc"),
          },
          {
            id: "offline",
            label: t("licenseActivationTabOffline"),
            description: t("licenseActivationTabOfflineDesc"),
          },
        ]}
      />
      {activeTab === "binding" && <DeploymentBindingPanel license={currentLicense} locale={locale} />}
      {activeTab === "offline" && (
        <OfflineActivationPanel
          actions={actions}
          activationRequest={activationRequest}
          canWriteLicense={canWriteLicense}
          licensePayload={licensePayload}
          localError={localError}
          localNotice={localNotice}
          onActivate={onActivate}
          onDownloadRequest={onDownloadRequest}
          setLicensePayload={setLicensePayload}
        />
      )}
    </div>
  );
}
