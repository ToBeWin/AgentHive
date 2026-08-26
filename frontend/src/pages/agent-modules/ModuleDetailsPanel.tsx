import { Boxes, CheckCircle2, Lock, Route } from "lucide-react";
import { useState } from "react";
import { Button, PageTabs, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { AgentModuleCatalogEntry } from "../../lib/api";
import { formatModuleState, formatState, getModuleIcon } from "./moduleCatalogUtils";

type ModuleDetailsTab = "summary" | "authorization" | "dependencies" | "rollout";

export function ModuleDetailsPanel({
  busy,
  module,
  onAction,
  onConfigure,
  onRequestLicense,
}: {
  busy: boolean;
  module: AgentModuleCatalogEntry | null;
  onAction: (moduleId: string, action: "install" | "enable" | "disable") => Promise<void>;
  onConfigure: (moduleId: string) => void;
  onRequestLicense: (moduleId: string) => void;
}) {
  const { t } = useLocale();
  const [activeTab, setActiveTab] = useState<ModuleDetailsTab>("summary");
  if (!module) {
    return (
      <section className="panel module-details-panel empty">
        <Boxes size={24} />
        <h2>{t("modulesDetailsEmptyTitle")}</h2>
        <p>{t("modulesDetailsEmptyMessage")}</p>
      </section>
    );
  }

  const Icon = getModuleIcon(module);
  const dependencies = module.dependencies ?? [];
  const missingFeatures = module.missing_features ?? [];
  const missingDependencies = module.missing_dependencies ?? [];
  const canManageModule =
    module.licensed && missingFeatures.length === 0 && missingDependencies.length === 0 && module.state !== "expired";

  return (
    <section className="panel module-details-panel">
      <div className="module-details-heading">
        <span className="module-icon">
          <Icon size={26} />
        </span>
        <div>
          <h2>{module.name}</h2>
          <p>{module.description || module.scenario}</p>
        </div>
        <StatusBadge status={formatState(module.state)} label={formatModuleState(module.state, t)} />
      </div>

      <div className="nested-workspace module-details-workspace">
        <PageTabs
          active={activeTab}
          onChange={setActiveTab}
          tabs={[
            {
              id: "summary",
              label: t("modulesDetailsTabSummary"),
              description: t("modulesDetailsTabSummaryDesc"),
            },
            {
              id: "authorization",
              label: t("modulesDetailsTabAuthorization"),
              description: t("modulesDetailsTabAuthorizationDesc"),
            },
            {
              id: "dependencies",
              label: t("modulesDetailsTabDependencies"),
              description: t("modulesDetailsTabDependenciesDesc"),
            },
            {
              id: "rollout",
              label: t("modulesDetailsTabRollout"),
              description: t("modulesDetailsTabRolloutDesc"),
            },
          ]}
        />

        {activeTab === "summary" && (
          <div className="module-details-grid">
            <DetailMetric label={t("modulesDetailsPriority")} value={module.priority} />
            <DetailMetric label={t("modulesDetailsVersion")} value={`v${module.version}`} />
            <DetailMetric label={t("modulesDetailsScenario")} value={module.scenario} />
            <DetailMetric
              label={t("modulesDetailsLicense")}
              value={module.licensed ? t("modulesLicensedForDeployment") : t("modulesNotIncluded")}
            />
          </div>
        )}

        {activeTab === "authorization" && (
          <ModuleChecklist
            checks={[
              {
                done: module.licensed,
                label: module.licensed ? t("modulesLicensedForDeployment") : t("modulesNotIncluded"),
                value: missingFeatures.length ? missingFeatures.join(", ") : t("modulesDetailsLicenseReady"),
              },
              {
                done: missingFeatures.length === 0,
                label: t("modulesMissingFeatures"),
                value: missingFeatures.length ? missingFeatures.join(", ") : t("modulesDetailsLicenseReady"),
              },
            ]}
          />
        )}

        {activeTab === "dependencies" && (
          <ModuleChecklist
            checks={[
              {
                done: missingDependencies.length === 0,
                label: t("modulesMissingDependencies"),
                value: missingDependencies.length
                  ? missingDependencies.join(", ")
                  : t("modulesDetailsDependenciesReady"),
              },
              {
                done: module.installed,
                label: t("modulesInstalled"),
                value: dependencies.length
                  ? `${t("modulesDependsOn")} ${dependencies.join(", ")}`
                  : t("modulesDetailsNoDependencies"),
              },
            ]}
          />
        )}

        {activeTab === "rollout" && (
          <>
            <ModuleChecklist
              checks={[
                {
                  done: canManageModule,
                  label: t("modulesDetailsManageable"),
                  value: canManageModule ? t("modulesDetailsReadyForInstance") : t("modulesDetailsResolveGaps"),
                },
                {
                  done: canManageModule && module.enabled,
                  label: t("modulesEnabled"),
                  value: module.enabled ? t("modulesDetailsPublished") : t("modulesDetailsEnableBeforeUse"),
                },
              ]}
            />
            <div className="card-actions module-details-actions">
              {canManageModule ? (
                <>
                  <Button disabled={!module.installed} onClick={() => onConfigure(module.id)}>
                    <Route size={15} /> {t("modulesConfigureInstance")}
                  </Button>
                  {module.state === "not_installed" ? (
                    <Button variant="primary" onClick={() => void onAction(module.id, "install")} disabled={busy}>
                      {busy ? t("modulesInstalling") : t("modulesInstall")}
                    </Button>
                  ) : module.state === "installed" || module.state === "disabled" ? (
                    <Button variant="primary" onClick={() => void onAction(module.id, "enable")} disabled={busy}>
                      {busy ? t("modulesEnabling") : t("modulesEnable")}
                    </Button>
                  ) : module.state === "enabled" ? (
                    <Button onClick={() => void onAction(module.id, "disable")} disabled={busy}>
                      {busy ? t("modulesDisabling") : t("modulesDisable")}
                    </Button>
                  ) : null}
                </>
              ) : (
                <Button onClick={() => onRequestLicense(module.id)}>
                  <Lock size={15} /> {t("modulesRequestLicense")}
                </Button>
              )}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

function DetailMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="module-detail-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ModuleChecklist({ checks }: { checks: Array<{ done: boolean; label: string; value: string }> }) {
  return (
    <div className="module-checklist">
      {checks.map((check) => (
        <div className={check.done ? "done" : ""} key={check.label}>
          <CheckCircle2 size={16} />
          <span>{check.label}</span>
          <small>{check.value}</small>
        </div>
      ))}
    </div>
  );
}
