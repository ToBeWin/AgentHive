import { AlertTriangle, CheckCircle2, type LucideIcon } from "lucide-react";
import { useState } from "react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { AuthorizedFeature, AuthorizedModule, LicenseStatusResponse } from "../../lib/api";

type ReadinessStatus = "ready" | "attention";

interface ReadinessItem {
  id: string;
  detail: string;
  icon: LucideIcon;
  label: string;
  metric: string;
  status: ReadinessStatus;
}

export function LicenseReadinessPanel({
  features,
  license,
  modules,
}: {
  features: AuthorizedFeature[];
  license: LicenseStatusResponse | null;
  modules: AuthorizedModule[];
}) {
  const { t } = useLocale();
  const enabledModules = modules.filter((module) => module.enabled).length;
  const enabledFeatures = features.filter((feature) => feature.enabled).length;
  const items: ReadinessItem[] = [
    {
      id: "license-active",
      label: t("licenseReadinessActive"),
      detail: t("licenseReadinessActiveDetail"),
      icon: license?.status === "active" ? CheckCircle2 : AlertTriangle,
      metric: license?.status === "active" ? t("licenseReadinessReadyMetric") : t("licenseReadinessAttentionMetric"),
      status: license?.status === "active" ? "ready" : "attention",
    },
    {
      id: "binding",
      label: t("licenseReadinessBinding"),
      detail: t("licenseReadinessBindingDetail"),
      icon: isDeploymentBound(license) ? CheckCircle2 : AlertTriangle,
      metric: isDeploymentBound(license) ? t("licenseReadinessReadyMetric") : t("licenseReadinessAttentionMetric"),
      status: isDeploymentBound(license) ? "ready" : "attention",
    },
    {
      id: "issues",
      label: t("licenseReadinessIssues"),
      detail: t("licenseReadinessIssuesDetail"),
      icon: license && license.verification_issues.length === 0 ? CheckCircle2 : AlertTriangle,
      metric:
        license && license.verification_issues.length === 0
          ? t("licenseReadinessReadyMetric")
          : t("licenseReadinessIssueMetric").replace("{{count}}", String(license?.verification_issues.length ?? 1)),
      status: license && license.verification_issues.length === 0 ? "ready" : "attention",
    },
    {
      id: "modules",
      label: t("licenseReadinessModules"),
      detail: `${enabledModules}/${modules.length} ${t("licenseReadinessModulesDetail")}`,
      icon: enabledModules > 0 ? CheckCircle2 : AlertTriangle,
      metric: `${enabledModules}/${modules.length}`,
      status: enabledModules > 0 ? "ready" : "attention",
    },
    {
      id: "features",
      label: t("licenseReadinessFeatures"),
      detail: `${enabledFeatures}/${features.length} ${t("licenseReadinessFeaturesDetail")}`,
      icon: enabledFeatures > 0 ? CheckCircle2 : AlertTriangle,
      metric: `${enabledFeatures}/${features.length}`,
      status: enabledFeatures > 0 ? "ready" : "attention",
    },
    {
      id: "maintenance",
      label: t("licenseReadinessMaintenance"),
      detail: t("licenseReadinessMaintenanceDetail"),
      icon: hasValidMaintenanceWindow(license?.maintenance_until ?? null) ? CheckCircle2 : AlertTriangle,
      metric: hasValidMaintenanceWindow(license?.maintenance_until ?? null)
        ? t("licenseReadinessReadyMetric")
        : t("licenseReadinessAttentionMetric"),
      status: hasValidMaintenanceWindow(license?.maintenance_until ?? null) ? "ready" : "attention",
    },
  ];
  const [selectedItemId, setSelectedItemId] = useState(() => items.find((item) => item.status === "attention")?.id);
  const readyCount = items.filter((item) => item.status === "ready").length;
  const attentionCount = items.length - readyCount;
  const selectedItem =
    items.find((item) => item.id === selectedItemId) ?? items.find((item) => item.status === "attention") ?? items[0];
  const SelectedIcon = selectedItem.icon;

  return (
    <section className="panel license-readiness-panel">
      <div className="panel-title">
        <div>
          <h2>
            {t("licenseReadinessTitle")} <span>{t("licenseReadinessAlt")}</span>
          </h2>
          <p>{t("licenseReadinessHelp")}</p>
        </div>
        <StatusBadge
          status={readyCount === items.length ? "READY" : "ATTENTION"}
          label={`${readyCount}/${items.length}`}
        />
      </div>
      <div className="license-readiness-summary">
        <StatusBadge label={t("licenseReadinessReadyCount").replace("{{count}}", String(readyCount))} status="ready" />
        <StatusBadge
          label={t("licenseReadinessAttentionCount").replace("{{count}}", String(attentionCount))}
          status="attention"
        />
      </div>
      <div className="license-readiness-workspace">
        <div className="license-readiness-steps" role="tablist" aria-label={t("licenseReadinessStageTabs")}>
          {items.map((item, index) => {
            const Icon = item.icon;
            const selected = selectedItem.id === item.id;
            return (
              <button
                aria-selected={selected}
                className={cx("license-readiness-step", item.status, selected && "selected")}
                key={item.id}
                onClick={() => setSelectedItemId(item.id)}
                role="tab"
                type="button"
              >
                <span className="license-readiness-index">{String(index + 1).padStart(2, "0")}</span>
                <span className="license-readiness-icon">
                  <Icon size={18} />
                </span>
                <span>
                  <strong>{item.label}</strong>
                  <small>{item.status === "ready" ? t("licenseReadinessReady") : t("licenseReadinessAttention")}</small>
                </span>
              </button>
            );
          })}
        </div>
        <section
          aria-label={t("licenseReadinessSelectedStage")}
          className={cx("license-readiness-detail", selectedItem.status)}
        >
          <div className="license-readiness-detail-head">
            <span className="license-readiness-icon">
              <SelectedIcon size={20} />
            </span>
            <div>
              <span>{t("licenseReadinessCurrentStage")}</span>
              <strong>{selectedItem.label}</strong>
            </div>
            <StatusBadge
              label={selectedItem.status === "ready" ? t("licenseReadinessReady") : t("licenseReadinessAttention")}
              status={selectedItem.status}
            />
          </div>
          <strong className="license-readiness-detail-metric">{selectedItem.metric}</strong>
          <p>{selectedItem.detail}</p>
        </section>
      </div>
    </section>
  );
}

function isDeploymentBound(license: LicenseStatusResponse | null): boolean {
  if (!license) {
    return false;
  }
  return (
    Boolean(license.deployment_id) &&
    license.deployment_id === license.runtime_deployment_id &&
    Boolean(license.install_id) &&
    license.install_id === license.runtime_install_id &&
    Boolean(license.machine_fingerprint_hash) &&
    license.machine_fingerprint_hash === license.runtime_machine_fingerprint_hash
  );
}

function hasValidMaintenanceWindow(value: string | null): boolean {
  if (!value) {
    return false;
  }
  const expiresAt = new Date(value).getTime();
  return Number.isFinite(expiresAt) && expiresAt > Date.now();
}
