import { Clipboard, FileCheck2, KeyRound, PackageCheck, Rocket, ShieldCheck, Wrench } from "lucide-react";
import { useState } from "react";
import { Button, cx, Panel, StatusBadge } from "../../components/app-ui";
import type { SystemDiagnostics } from "../../hooks/admin/system";
import { useLocale } from "../../i18n-context";
import type { SystemComponentReport } from "../../lib/api";
import { deliveryStatusLabel } from "./settingsUtils";

type DeliveryCenterTab = "setup" | "rollout" | "acceptance";
type DeliveryStepState = "done" | "review" | "blocked";

interface DeliveryAction {
  command?: string;
  detail: string;
  group: DeliveryCenterTab;
  id: string;
  state: DeliveryStepState;
  title: string;
  icon: typeof Rocket;
}

interface DeliveryPhase {
  actions: DeliveryAction[];
  description: string;
  id: DeliveryCenterTab;
  label: string;
}

const INSTALL_COMMAND = "scripts/install.sh --license-public-key ./agenthive_license_public.pem --start";
const DIAGNOSTICS_COMMAND = 'scripts/diagnose.sh --strict --output-dir "diagnostics/$(date -u +%Y%m%dT%H%M%SZ)"';
const UPGRADE_COMMAND = 'scripts/upgrade.sh --diagnostics-output-dir "diagnostics/upgrade-$(date -u +%Y%m%dT%H%M%SZ)"';

export function DeliveryCenterPanel({ diagnostics }: { diagnostics: SystemDiagnostics | null }) {
  const { t } = useLocale();
  const [activeTab, setActiveTab] = useState<DeliveryCenterTab>("setup");
  const [copiedCommandId, setCopiedCommandId] = useState<string | null>(null);
  const components = diagnostics?.readiness.components ?? {};
  const delivery = diagnostics?.readiness.delivery ?? null;
  const actions = buildActions(components, delivery?.status, t);
  const phases = buildPhases(actions, t);
  const visibleActions = actions.filter((action) => action.group === activeTab);
  const doneCount = actions.filter((action) => action.state === "done").length;
  const blockedCount = actions.filter((action) => action.state === "blocked").length;

  const copyCommand = async (action: DeliveryAction) => {
    if (!action.command) {
      return;
    }
    await navigator.clipboard?.writeText(action.command);
    setCopiedCommandId(action.id);
  };

  return (
    <Panel
      title={t("settingsDeliveryCenter")}
      subtitle={t("settingsDeliveryCenterHelp")}
      actions={
        <StatusBadge
          status={blockedCount > 0 ? "blocked" : doneCount === actions.length ? "healthy" : "degraded"}
          label={`${doneCount}/${actions.length}`}
        />
      }
      className="settings-delivery-center"
    >
      <div className="settings-delivery-center-summary">
        <span>
          <strong>{delivery ? deliveryStatusLabel(delivery.status, t) : t("settingsDeliveryUnavailable")}</strong>
          {t("settingsDeliveryCenterStatus")}
        </span>
        <span>
          <strong>{blockedCount}</strong>
          {t("settingsDeliveryCenterBlocked")}
        </span>
      </div>
      <div className="nested-workspace settings-delivery-center-workspace">
        <div className="settings-delivery-phase-strip" role="tablist" aria-label={t("settingsDeliveryCenterPhases")}>
          {phases.map((phase) => {
            const phaseDoneCount = phase.actions.filter((action) => action.state === "done").length;
            const phaseBlockedCount = phase.actions.filter((action) => action.state === "blocked").length;
            const phaseStatus =
              phaseBlockedCount > 0 ? "unhealthy" : phaseDoneCount === phase.actions.length ? "healthy" : "degraded";

            return (
              <button
                aria-selected={activeTab === phase.id}
                className={cx("settings-delivery-phase", activeTab === phase.id && "active")}
                key={phase.id}
                onClick={() => setActiveTab(phase.id)}
                role="tab"
                type="button"
              >
                <span>
                  <strong>{phase.label}</strong>
                  <small>{phase.description}</small>
                </span>
                <span className="settings-delivery-phase-meta">
                  <StatusBadge status={phaseStatus} label={`${phaseDoneCount}/${phase.actions.length}`} />
                  {phaseBlockedCount > 0 && <em>{phaseBlockedCount}</em>}
                </span>
              </button>
            );
          })}
        </div>
        <div className="settings-delivery-center-grid">
          {visibleActions.map((action) => (
            <article
              className={cx("settings-delivery-action", `settings-delivery-action-${action.state}`)}
              key={action.id}
            >
              <action.icon size={18} />
              <div>
                <strong>{action.title}</strong>
                <p>{action.detail}</p>
                {action.command && <code className="settings-delivery-command">{action.command}</code>}
              </div>
              <div className="settings-delivery-action-side">
                <StatusBadge status={statusForState(action.state)} label={labelForState(action.state, t)} />
                {action.command && (
                  <Button variant="ghost" onClick={() => void copyCommand(action)}>
                    <Clipboard size={15} />{" "}
                    {copiedCommandId === action.id
                      ? t("settingsDeliveryCommandCopied")
                      : t("settingsDeliveryCommandCopy")}
                  </Button>
                )}
              </div>
            </article>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function buildPhases(actions: DeliveryAction[], t: (key: string) => string): DeliveryPhase[] {
  const phaseLabels: Record<DeliveryCenterTab, { description: string; label: string }> = {
    acceptance: {
      description: t("settingsDeliveryCenterTabAcceptanceDesc"),
      label: t("settingsDeliveryCenterTabAcceptance"),
    },
    rollout: {
      description: t("settingsDeliveryCenterTabRolloutDesc"),
      label: t("settingsDeliveryCenterTabRollout"),
    },
    setup: {
      description: t("settingsDeliveryCenterTabSetupDesc"),
      label: t("settingsDeliveryCenterTabSetup"),
    },
  };

  return (["setup", "rollout", "acceptance"] as const).map((phase) => ({
    actions: actions.filter((action) => action.group === phase),
    description: phaseLabels[phase].description,
    id: phase,
    label: phaseLabels[phase].label,
  }));
}

function buildActions(
  components: Record<string, SystemComponentReport>,
  deliveryStatus: string | undefined,
  t: (key: string) => string,
): DeliveryAction[] {
  return [
    {
      command: INSTALL_COMMAND,
      detail: t("settingsDeliveryCenterInstallDetail"),
      group: "setup",
      icon: Rocket,
      id: "install",
      state: stateFromComponents(components, ["database", "redis", "minio", "license_identity", "production_config"]),
      title: t("settingsDeliveryCenterInstall"),
    },
    {
      detail: t("settingsDeliveryCenterLicenseDetail"),
      group: "setup",
      icon: KeyRound,
      id: "license",
      state: stateFromComponents(components, ["license_identity"]),
      title: t("settingsDeliveryCenterLicense"),
    },
    {
      detail: t("settingsDeliveryCenterModelsDetail"),
      group: "rollout",
      icon: Wrench,
      id: "models",
      state: stateFromComponents(components, ["litellm"]),
      title: t("settingsDeliveryCenterModels"),
    },
    {
      detail: t("settingsDeliveryCenterAgentsDetail"),
      group: "rollout",
      icon: PackageCheck,
      id: "agents",
      state: stateFromComponents(components, ["knowledge_runtime", "channel_gateway", "budget_governance"]),
      title: t("settingsDeliveryCenterAgents"),
    },
    {
      command: DIAGNOSTICS_COMMAND,
      detail: t("settingsDeliveryCenterDiagnosticsDetail"),
      group: "acceptance",
      icon: FileCheck2,
      id: "diagnostics",
      state: deliveryStatus === "blocked" ? "blocked" : deliveryStatus ? "done" : "review",
      title: t("settingsDeliveryCenterDiagnostics"),
    },
    {
      command: UPGRADE_COMMAND,
      detail: t("settingsDeliveryCenterUpgradeDetail"),
      group: "acceptance",
      icon: ShieldCheck,
      id: "upgrade",
      state: stateFromComponents(components, ["license_identity", "production_config"]),
      title: t("settingsDeliveryCenterUpgrade"),
    },
  ];
}

function stateFromComponents(components: Record<string, SystemComponentReport>, keys: string[]): DeliveryStepState {
  const reports = keys.map((key) => components[key]).filter(Boolean);
  if (!reports.length) {
    return "review";
  }
  if (reports.some((report) => report.status === "unhealthy" || report.status === "error")) {
    return "blocked";
  }
  if (reports.some((report) => report.status === "degraded" || report.status === "not_configured")) {
    return "review";
  }
  return "done";
}

function labelForState(state: DeliveryStepState, t: (key: string) => string) {
  if (state === "done") {
    return t("settingsChecklistDone");
  }
  if (state === "blocked") {
    return t("settingsChecklistBlocked");
  }
  return t("settingsChecklistReview");
}

function statusForState(state: DeliveryStepState) {
  if (state === "done") {
    return "healthy";
  }
  if (state === "blocked") {
    return "unhealthy";
  }
  return "degraded";
}
