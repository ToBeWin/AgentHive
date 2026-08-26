import { Lock } from "lucide-react";
import { Button, cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { AgentModuleCatalogEntry } from "../../lib/api";
import { formatModuleState, formatState, getModuleIcon } from "./moduleCatalogUtils";

export function ModuleCard({
  busy,
  module,
  onAction,
  onConfigure,
  onRequestLicense,
  onSelect,
  selected,
}: {
  busy: boolean;
  module: AgentModuleCatalogEntry;
  onAction: (moduleId: string, action: "install" | "enable" | "disable") => Promise<void>;
  onConfigure: (moduleId: string) => void;
  onRequestLicense: (moduleId: string) => void;
  onSelect: (moduleId: string) => void;
  selected: boolean;
}) {
  const { t } = useLocale();
  const Icon = getModuleIcon(module);
  const dependencies = module.dependencies ?? [];
  const missingFeatures = module.missing_features ?? [];
  const missingDependencies = module.missing_dependencies ?? [];
  const canManageModule =
    module.licensed && missingFeatures.length === 0 && missingDependencies.length === 0 && module.state !== "expired";

  return (
    <article className={cx("module-card", !canManageModule && "muted-card", selected && "selected")} key={module.id}>
      <div className="card-top">
        <div className="module-icon">
          <Icon size={26} />
        </div>
        <StatusBadge status={formatState(module.state)} label={formatModuleState(module.state, t)} />
      </div>
      <h2>{module.name}</h2>
      <p>{module.description || module.scenario}</p>
      <div className="module-meta">
        <code>{module.priority}</code>
        <span>v{module.version}</span>
        <span>{module.scenario}</span>
      </div>
      <div className="module-license-row">
        <span>
          {missingFeatures.length
            ? t("modulesMissingFeatures")
            : missingDependencies.length
              ? t("modulesMissingDependencies")
              : module.licensed
                ? t("modulesLicensedForDeployment")
                : t("modulesNotIncluded")}
        </span>
        <strong>
          {module.enabled ? t("modulesEnabled") : module.installed ? t("modulesInstalled") : t("modulesOptional")}
        </strong>
      </div>
      {missingFeatures.length > 0 && (
        <small className="module-dependencies">
          {t("modulesMissingFeaturesList")} {missingFeatures.join(", ")}
        </small>
      )}
      {missingDependencies.length > 0 && (
        <small className="module-dependencies">
          {t("modulesMissingDependenciesList")} {missingDependencies.join(", ")}
        </small>
      )}
      {dependencies.length > 0 && (
        <small className="module-dependencies">
          {t("modulesDependsOn")} {dependencies.join(", ")}
        </small>
      )}
      <div className="card-actions">
        <Button onClick={() => onSelect(module.id)}>{t("modulesViewDetails")}</Button>
        {canManageModule ? (
          <>
            <Button disabled={!module.installed} onClick={() => onConfigure(module.id)}>
              {t("commonConfigure")}
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
    </article>
  );
}
