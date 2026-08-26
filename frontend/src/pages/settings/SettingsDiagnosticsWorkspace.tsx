import { PageTabs } from "../../components/app-ui";
import type { SystemDiagnostics } from "../../hooks/admin/system";
import { useLocale } from "../../i18n-context";
import { AgentConcurrencyPanel } from "./AgentConcurrencyPanel";
import { DeploymentIdentityPanel } from "./DeploymentIdentityPanel";
import { ProductionConfigPanel } from "./ProductionConfigPanel";
import { PrototypeDemoPanel } from "./PrototypeDemoPanel";
import { SystemComponentTable } from "./SystemComponentTable";
import type { DiagnosticsStageTab } from "./settingsWorkspaceTypes";

export function SettingsDiagnosticsWorkspace({
  activeStage,
  diagnostics,
  isPrototype,
  onStageChange,
}: {
  activeStage: DiagnosticsStageTab;
  diagnostics: SystemDiagnostics | null;
  isPrototype: boolean;
  onStageChange: (stage: DiagnosticsStageTab) => void;
}) {
  const { t } = useLocale();
  const readiness = diagnostics?.readiness ?? null;
  const health = diagnostics?.health ?? null;
  const info = diagnostics?.info ?? null;
  const licenseIdentity = readiness?.components.license_identity ?? health?.components.license_identity ?? null;
  const productionConfig = readiness?.components.production_config ?? health?.components.production_config ?? null;

  return (
    <div className="settings-diagnostics-workspace">
      <PageTabs
        active={activeStage}
        onChange={onStageChange}
        tabs={[
          {
            id: "components",
            label: t("settingsDiagnosticsStageComponents"),
            description: t("settingsDiagnosticsStageComponentsDesc"),
          },
          {
            id: "identity",
            label: t("settingsDiagnosticsStageIdentity"),
            description: t("settingsDiagnosticsStageIdentityDesc"),
          },
        ]}
      />
      {activeStage === "components" && (
        <div className="stack">
          <AgentConcurrencyPanel report={readiness ?? health} />
          <SystemComponentTable report={readiness} />
        </div>
      )}
      {activeStage === "identity" && (
        <div className="stack">
          <DeploymentIdentityPanel info={info} licenseIdentity={licenseIdentity} />
          <ProductionConfigPanel report={productionConfig} />
          {isPrototype && <PrototypeDemoPanel />}
        </div>
      )}
    </div>
  );
}
