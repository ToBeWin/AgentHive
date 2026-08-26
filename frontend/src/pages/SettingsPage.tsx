import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { ApiNotice, Button, PageHeader, PageTabs } from "../components/app-ui";
import { useSystemDiagnostics } from "../hooks/useAdminData";
import { useLocale } from "../i18n-context";
import type { AuthUser } from "../lib/api";
import { RoleWorkspacePanel } from "./settings/RoleWorkspacePanel";
import { SettingsDeliveryWorkspace } from "./settings/SettingsDeliveryWorkspace";
import { SettingsDiagnosticsWorkspace } from "./settings/SettingsDiagnosticsWorkspace";
import { SettingsExportsWorkspace } from "./settings/SettingsExportsWorkspace";
import { SettingsRoleNavigator } from "./settings/SettingsRoleNavigator";
import { SettingsSummaryGrid } from "./settings/SettingsSummaryGrid";
import type {
  DeliveryStageTab,
  DiagnosticsStageTab,
  ExportsStageTab,
  SettingsPageTab,
} from "./settings/settingsWorkspaceTypes";

export function SettingsPage({ isPrototype, user }: { isPrototype: boolean; user: AuthUser | null }) {
  const diagnostics = useSystemDiagnostics({ fallbackOnError: isPrototype });
  const { locale, t } = useLocale();
  const [activeTab, setActiveTab] = useState<SettingsPageTab>("delivery");
  const [deliveryStage, setDeliveryStage] = useState<DeliveryStageTab>("overview");
  const [diagnosticsStage, setDiagnosticsStage] = useState<DiagnosticsStageTab>("components");
  const [exportsStage, setExportsStage] = useState<ExportsStageTab>("acceptance");
  const data = diagnostics.data;
  const openSettingsTab = (tab: SettingsPageTab) => {
    setActiveTab(tab);
  };

  return (
    <section className="page settings-page">
      <PageHeader
        title={t("settingsTitle")}
        subtitle={t("settingsSubtitle")}
        actions={
          <Button onClick={diagnostics.refetch} disabled={diagnostics.loading}>
            <RefreshCw size={16} /> {diagnostics.loading ? t("settingsRefreshing") : t("settingsRefresh")}
          </Button>
        }
      />
      {diagnostics.error && !diagnostics.loading && (
        <ApiNotice
          title={t("settingsDiagnosticsUnavailable")}
          message={diagnostics.error}
          action={<Button onClick={diagnostics.refetch}>{t("commonRetry")}</Button>}
        />
      )}
      <SettingsSummaryGrid diagnostics={data} locale={locale} t={t} />
      <SettingsRoleNavigator activeTab={activeTab} diagnostics={data} onOpenTab={openSettingsTab} />
      <PageTabs
        active={activeTab}
        onChange={setActiveTab}
        tabs={[
          { id: "delivery", label: t("settingsTabDelivery"), description: t("settingsTabDeliveryDesc") },
          { id: "roles", label: t("settingsTabRoles"), description: t("settingsTabRolesDesc") },
          { id: "diagnostics", label: t("settingsTabDiagnostics"), description: t("settingsTabDiagnosticsDesc") },
          { id: "exports", label: t("settingsTabExports"), description: t("settingsTabExportsDesc") },
        ]}
      />
      {activeTab === "delivery" && (
        <SettingsDeliveryWorkspace
          activeStage={deliveryStage}
          diagnostics={data}
          isPrototype={isPrototype}
          onStageChange={setDeliveryStage}
        />
      )}
      {activeTab === "roles" && <RoleWorkspacePanel isPrototype={isPrototype} user={user} />}
      {activeTab === "diagnostics" && (
        <SettingsDiagnosticsWorkspace
          activeStage={diagnosticsStage}
          diagnostics={data}
          isPrototype={isPrototype}
          onStageChange={setDiagnosticsStage}
        />
      )}
      {activeTab === "exports" && (
        <SettingsExportsWorkspace
          activeStage={exportsStage}
          diagnostics={data}
          isPrototype={isPrototype}
          onStageChange={setExportsStage}
          user={user}
        />
      )}
    </section>
  );
}
