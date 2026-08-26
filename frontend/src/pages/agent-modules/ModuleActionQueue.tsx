import { CheckCircle2, Lock, Route } from "lucide-react";
import { Button } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { AgentModuleCatalogEntry } from "../../lib/api";
import { formatModuleState, getModuleIcon } from "./moduleCatalogUtils";

export function ModuleActionQueue({
  busyModuleId,
  modules,
  onAction,
  onConfigure,
  onRequestLicense,
  onSelect,
}: {
  busyModuleId: string | null;
  modules: AgentModuleCatalogEntry[];
  onAction: (moduleId: string, action: "install" | "enable" | "disable") => Promise<void>;
  onConfigure: (moduleId: string) => void;
  onRequestLicense: (moduleId: string) => void;
  onSelect: (moduleId: string) => void;
}) {
  const { t } = useLocale();
  const queue = buildModuleActionQueue(modules, t).slice(0, 4);

  return (
    <section className="module-action-queue" aria-label={t("modulesQueueTitle")}>
      <div className="module-action-queue-heading">
        <div>
          <h2>{t("modulesQueueTitle")}</h2>
          <p>{queue.length ? t("modulesQueueSubtitle") : t("modulesQueueDoneMessage")}</p>
        </div>
        <span>
          {queue.length
            ? t("modulesQueueCount").replace("{{count}}", String(queue.length))
            : t("modulesQueueDoneTitle")}
        </span>
      </div>
      <div className="module-action-queue-list">
        {queue.length ? (
          queue.map((item) => {
            const Icon = getModuleIcon(item.module);
            const busy = busyModuleId === item.module.id;
            return (
              <article className="module-action-item" key={item.module.id}>
                <span className="module-action-icon">
                  <Icon size={18} />
                </span>
                <div>
                  <strong>{item.module.name}</strong>
                  <small>{item.reason}</small>
                </div>
                <Button onClick={() => onSelect(item.module.id)}>{t("modulesViewDetails")}</Button>
                {item.action === "license" && (
                  <Button onClick={() => onRequestLicense(item.module.id)}>
                    <Lock size={15} /> {t("modulesRequestLicense")}
                  </Button>
                )}
                {item.action === "install" && (
                  <Button variant="primary" disabled={busy} onClick={() => void onAction(item.module.id, "install")}>
                    {busy ? t("modulesInstalling") : t("modulesInstall")}
                  </Button>
                )}
                {item.action === "enable" && (
                  <Button variant="primary" disabled={busy} onClick={() => void onAction(item.module.id, "enable")}>
                    {busy ? t("modulesEnabling") : t("modulesEnable")}
                  </Button>
                )}
                {item.action === "configure" && (
                  <Button onClick={() => onConfigure(item.module.id)}>
                    <Route size={15} /> {t("modulesConfigureInstance")}
                  </Button>
                )}
              </article>
            );
          })
        ) : (
          <div className="module-action-empty">
            <CheckCircle2 size={18} />
            <span>{t("modulesQueueDoneMessage")}</span>
          </div>
        )}
      </div>
    </section>
  );
}

function buildModuleActionQueue(modules: AgentModuleCatalogEntry[], t: (key: string) => string) {
  return modules
    .map((module) => {
      const missingFeatures = module.missing_features ?? [];
      const missingDependencies = module.missing_dependencies ?? [];
      if (!module.licensed || module.state === "not_licensed" || module.state === "expired") {
        return {
          action: "license" as const,
          module,
          reason: module.state === "expired" ? t("modulesQueueExpired") : t("modulesQueueNeedsLicense"),
          rank: 1,
        };
      }
      if (missingFeatures.length > 0 || missingDependencies.length > 0) {
        return {
          action: "license" as const,
          module,
          reason: [missingFeatures.join(", "), missingDependencies.join(", ")].filter(Boolean).join(" / "),
          rank: 2,
        };
      }
      if (module.state === "not_installed") {
        return { action: "install" as const, module, reason: t("modulesQueueNeedsInstall"), rank: 3 };
      }
      if (module.state === "installed" || module.state === "disabled") {
        return {
          action: "enable" as const,
          module,
          reason: `${t("modulesQueueNeedsEnable")} · ${formatModuleState(module.state, t)}`,
          rank: 4,
        };
      }
      if (module.enabled && module.installed) {
        return { action: "configure" as const, module, reason: t("modulesQueueReadyConfigure"), rank: 5 };
      }
      return null;
    })
    .filter((item): item is NonNullable<typeof item> => Boolean(item))
    .sort((left, right) => left.rank - right.rank || left.module.priority.localeCompare(right.module.priority));
}
