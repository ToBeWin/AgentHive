import { PageTabs } from "../../components/app-ui";
import type { SystemDiagnostics } from "../../hooks/admin/system";
import { useLocale } from "../../i18n-context";
import { DeliveryAcceptanceOverviewPanel } from "./DeliveryAcceptanceOverviewPanel";
import { DeliveryCenterPanel } from "./DeliveryCenterPanel";
import { DeliveryReadinessPanel } from "./DeliveryReadinessPanel";
import { DeploymentChecklistPanel } from "./DeploymentChecklistPanel";
import type { DeliveryStageTab } from "./settingsWorkspaceTypes";

export function SettingsDeliveryWorkspace({
  activeStage,
  diagnostics,
  isPrototype,
  onStageChange,
}: {
  activeStage: DeliveryStageTab;
  diagnostics: SystemDiagnostics | null;
  isPrototype: boolean;
  onStageChange: (stage: DeliveryStageTab) => void;
}) {
  const { t } = useLocale();
  const delivery = diagnostics?.readiness.delivery ?? null;

  return (
    <div className="settings-delivery-workspace">
      <PageTabs
        active={activeStage}
        onChange={onStageChange}
        tabs={[
          {
            id: "overview",
            label: t("settingsDeliveryStageOverview"),
            description: t("settingsDeliveryStageOverviewDesc"),
          },
          {
            id: "readiness",
            label: t("settingsDeliveryStageReadiness"),
            description: t("settingsDeliveryStageReadinessDesc"),
          },
          {
            id: "workflow",
            label: t("settingsDeliveryStageWorkflow"),
            description: t("settingsDeliveryStageWorkflowDesc"),
          },
          {
            id: "checklist",
            label: t("settingsDeliveryStageChecklist"),
            description: t("settingsDeliveryStageChecklistDesc"),
          },
        ]}
      />
      {activeStage === "overview" && <DeliveryAcceptanceOverviewPanel diagnostics={diagnostics} />}
      {activeStage === "readiness" && <DeliveryReadinessPanel delivery={delivery} />}
      {activeStage === "workflow" && <DeliveryCenterPanel diagnostics={diagnostics} />}
      {activeStage === "checklist" && <DeploymentChecklistPanel diagnostics={diagnostics} isPrototype={isPrototype} />}
    </div>
  );
}
