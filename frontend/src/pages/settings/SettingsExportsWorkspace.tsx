import { PageTabs } from "../../components/app-ui";
import type { SystemDiagnostics } from "../../hooks/admin/system";
import { useLocale } from "../../i18n-context";
import type { AuthUser } from "../../lib/api";
import { AcceptanceReportPanel } from "./AcceptanceReportPanel";
import { DiagnosticsExportPanel } from "./DiagnosticsExportPanel";
import type { ExportsStageTab } from "./settingsWorkspaceTypes";

export function SettingsExportsWorkspace({
  activeStage,
  diagnostics,
  isPrototype,
  onStageChange,
  user,
}: {
  activeStage: ExportsStageTab;
  diagnostics: SystemDiagnostics | null;
  isPrototype: boolean;
  onStageChange: (stage: ExportsStageTab) => void;
  user: AuthUser | null;
}) {
  const { t } = useLocale();

  return (
    <div className="settings-diagnostics-workspace">
      <PageTabs
        active={activeStage}
        onChange={onStageChange}
        tabs={[
          {
            id: "acceptance",
            label: t("settingsExportsStageAcceptance"),
            description: t("settingsExportsStageAcceptanceDesc"),
          },
          {
            id: "support",
            label: t("settingsExportsStageSupport"),
            description: t("settingsExportsStageSupportDesc"),
          },
        ]}
      />
      {activeStage === "acceptance" && <AcceptanceReportPanel diagnostics={diagnostics} />}
      {activeStage === "support" && (
        <DiagnosticsExportPanel diagnostics={diagnostics} isPrototype={isPrototype} user={user} />
      )}
    </div>
  );
}
