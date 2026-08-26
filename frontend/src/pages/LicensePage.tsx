import { ShieldOff, SlidersHorizontal } from "lucide-react";
import { useMemo, useState } from "react";
import { ApiNotice, Button, ConfirmDialog, PageHeader, PageTabs } from "../components/app-ui";
import { useLicenseActivationActions, useLicenseModules, useLicenseStatus } from "../hooks/useAdminData";
import { useLocale } from "../i18n-context";
import type { ActivationRequestResponse, AuthUser } from "../lib/api";
import { downloadTextFile } from "../lib/download";
import { canAccess } from "../lib/permissions";
import { AuthorizedScopePanel } from "./license/AuthorizedScopePanel";
import { LicenseActivationWorkspace } from "./license/LicenseActivationWorkspace";
import { LicenseStatusWorkspace } from "./license/LicenseStatusWorkspace";
import { summarizeScope } from "./license/licenseUtils";
import type { LicenseActivationTab, LicensePageTab, LicenseStatusTab } from "./license/licenseWorkspaceTypes";

const LICENSE_WRITE_PERMISSION = "license:write";
const LICENSE_TAB_REQUEST_KEY = "agenthive.license.default_tab";

function consumeRequestedLicenseTab(): LicensePageTab {
  const requested = window.sessionStorage.getItem(LICENSE_TAB_REQUEST_KEY);
  if (requested === "status" || requested === "activation" || requested === "scope") {
    window.sessionStorage.removeItem(LICENSE_TAB_REQUEST_KEY);
    return requested;
  }
  return "status";
}

export function LicensePage({ isPrototype = false, user }: { isPrototype?: boolean; user: AuthUser | null }) {
  const { locale, t } = useLocale();
  const licenseStatus = useLicenseStatus({ fallbackOnError: isPrototype });
  const licenseModules = useLicenseModules({ fallbackOnError: isPrototype });
  const licenseActions = useLicenseActivationActions({ fallbackOnError: isPrototype });
  const [activationRequest, setActivationRequest] = useState<ActivationRequestResponse | null>(null);
  const [licensePayload, setLicensePayload] = useState("");
  const requestedTab = useMemo(consumeRequestedLicenseTab, []);
  const [localNotice, setLocalNotice] = useState<string | null>(() =>
    requestedTab === "scope" ? t("licenseScopeFocusedNotice") : null,
  );
  const [localError, setLocalError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<LicensePageTab>(requestedTab);
  const [statusTab, setStatusTab] = useState<LicenseStatusTab>("overview");
  const [activationTab, setActivationTab] = useState<LicenseActivationTab>("binding");
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);

  const license = licenseStatus.data;
  const scope = licenseModules.data;
  const modules = scope?.modules ?? [];
  const features = scope?.features ?? [];
  const scopeSummary = useMemo(() => summarizeScope(modules, features), [modules, features]);
  const canWriteLicense = isPrototype || canAccess(user, [LICENSE_WRITE_PERMISSION]);

  const syncLicense = async () => {
    setLocalNotice(null);
    setLocalError(null);
    await Promise.all([licenseStatus.refetch(), licenseModules.refetch()]);
    setLocalNotice(t("licenseSyncedNotice"));
  };

  const downloadActivationRequest = async () => {
    setLocalNotice(null);
    setLocalError(null);
    const request = await licenseActions.getActivationRequest();
    if (!request) {
      return;
    }
    setActivationRequest(request);
    downloadTextFile(
      JSON.stringify(request, null, 2),
      `agenthive-activation-request-${request.request_id}.json`,
      "application/json;charset=utf-8",
    );
    setLocalNotice(t("licenseDownloadNotice"));
  };

  const activateLicense = async () => {
    setLocalNotice(null);
    setLocalError(null);
    if (!canWriteLicense) {
      setLocalError(t("licenseWritePermissionRequired"));
      return;
    }
    const trimmedPayload = licensePayload.trim();
    if (!trimmedPayload) {
      setLocalError(t("licenseActivationRequired"));
      return;
    }
    const response = await licenseActions.activateLicense(trimmedPayload);
    if (!response) {
      return;
    }
    setLicensePayload("");
    await syncLicense();
    setLocalNotice(response.message || t("licenseActivatedNotice"));
    setActiveTab("status");
  };

  const requestDeactivateLicense = () => {
    setLocalNotice(null);
    setLocalError(null);
    if (!canWriteLicense) {
      setLocalError(t("licenseWritePermissionRequired"));
      return;
    }
    setConfirmDeactivate(true);
  };

  const deactivateLicense = async () => {
    setConfirmDeactivate(false);
    const response = await licenseActions.deactivateLicense();
    if (!response) {
      return;
    }
    await syncLicense();
    setLocalNotice(response.message || t("licenseDeactivatedNotice"));
  };

  return (
    <section className="page license-page">
      <PageHeader
        title={t("licenseTitle")}
        subtitle={t("licenseSubtitle")}
        actions={
          <>
            {canWriteLicense && (
              <Button
                onClick={requestDeactivateLicense}
                disabled={licenseActions.deactivating || licenseStatus.loading}
              >
                <ShieldOff size={16} />{" "}
                {licenseActions.deactivating ? t("licenseDeactivating") : t("licenseDeactivate")}
              </Button>
            )}
            <Button onClick={syncLicense} disabled={licenseStatus.loading || licenseModules.loading}>
              <SlidersHorizontal size={16} /> {t("syncLicense")}
            </Button>
          </>
        }
      />
      {licenseStatus.loading && <ApiNotice title={t("licenseLoadingTitle")} message={t("licenseLoadingMessage")} />}
      {licenseStatus.error && !licenseStatus.loading && (
        <ApiNotice
          title={t("licenseLoadErrorTitle")}
          message={licenseStatus.error}
          action={<Button onClick={licenseStatus.refetch}>{t("commonRetry")}</Button>}
        />
      )}
      {localNotice && activeTab !== "activation" && <div className="form-message">{localNotice}</div>}
      {localError && activeTab !== "activation" && <div className="form-message error">{localError}</div>}
      <PageTabs
        active={activeTab}
        onChange={setActiveTab}
        tabs={[
          { id: "status", label: t("licenseTabStatus"), description: t("licenseTabStatusDesc") },
          { id: "activation", label: t("licenseTabActivation"), description: t("licenseTabActivationDesc") },
          { id: "scope", label: t("licenseTabScope"), description: t("licenseTabScopeDesc") },
        ]}
      />
      {activeTab === "status" && (
        <LicenseStatusWorkspace
          activeTab={statusTab}
          features={features}
          license={license}
          locale={locale}
          modules={modules}
          onTabChange={setStatusTab}
          scopeSummary={scopeSummary}
        />
      )}
      {activeTab === "activation" && (
        <LicenseActivationWorkspace
          actions={licenseActions}
          activationRequest={activationRequest}
          activeTab={activationTab}
          canWriteLicense={canWriteLicense}
          license={license}
          licensePayload={licensePayload}
          locale={locale}
          localError={localError}
          localNotice={localNotice}
          onActivate={() => void activateLicense()}
          onDownloadRequest={() => void downloadActivationRequest()}
          onTabChange={setActivationTab}
          setLicensePayload={setLicensePayload}
        />
      )}
      {activeTab === "scope" && (
        <AuthorizedScopePanel
          error={licenseModules.error}
          features={features}
          loading={licenseModules.loading}
          modules={modules}
          scopeLoaded={Boolean(scope)}
          summaryEnabledModules={scopeSummary.enabledModules}
          onRetry={licenseModules.refetch}
        />
      )}
      <ConfirmDialog
        open={confirmDeactivate}
        title={t("licenseDeactivate")}
        message={t("licenseDeactivateConfirm")}
        confirmLabel={t("licenseDeactivate")}
        cancelLabel={t("commonClose")}
        variant="danger"
        onConfirm={() => void deactivateLicense()}
        onCancel={() => setConfirmDeactivate(false)}
      />
    </section>
  );
}
