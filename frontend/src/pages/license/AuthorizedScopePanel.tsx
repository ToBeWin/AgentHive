import { KeyRound } from "lucide-react";
import { useState } from "react";
import { ApiNotice, Button, cx, LoadingState, PageTabs, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { AuthorizedFeature, AuthorizedModule } from "../../lib/api";
import { formatModuleState, formatState } from "../agent-modules/moduleCatalogUtils";

type ScopeTab = "modules" | "features";

export function AuthorizedScopePanel({
  error,
  features,
  loading,
  modules,
  onRetry,
  scopeLoaded,
  summaryEnabledModules,
}: {
  error: string | null;
  features: AuthorizedFeature[];
  loading: boolean;
  modules: AuthorizedModule[];
  onRetry: () => void;
  scopeLoaded: boolean;
  summaryEnabledModules: number;
}) {
  const { t } = useLocale();
  const [scopeTab, setScopeTab] = useState<ScopeTab>("modules");
  return (
    <section className="panel">
      <div className="panel-title">
        <div>
          <h2>
            {t("licenseAuthorizedScope")} <span>{t("licenseAuthorizedScopeAlt")}</span>
          </h2>
          <p>{t("licenseAuthorizedScopeHelp")}</p>
        </div>
        <StatusBadge
          status={`${summaryEnabledModules} MODULES ENABLED`}
          label={`${summaryEnabledModules} ${t("licenseModulesEnabledBadge")}`}
        />
      </div>
      {loading && <LoadingState message={t("licenseLoadingScopeMessage")} lines={3} />}
      {error && !loading && (
        <ApiNotice
          title={t("licenseScopeErrorTitle")}
          message={error}
          action={<Button onClick={onRetry}>{t("commonRetry")}</Button>}
        />
      )}
      {!loading && !error && scopeLoaded && modules.length === 0 && features.length === 0 && (
        <ApiNotice title={t("licenseNoScopeTitle")} message={t("licenseNoScopeMessage")} />
      )}
      <div className="nested-workspace license-scope-workspace">
        <PageTabs
          active={scopeTab}
          onChange={setScopeTab}
          tabs={[
            {
              id: "modules",
              label: `${t("licenseAgentModules")} ${modules.length}`,
              description: t("licenseAgentModulesTabDesc"),
            },
            {
              id: "features",
              label: `${t("licenseCoreFeatures")} ${features.length}`,
              description: t("licenseCoreFeaturesTabDesc"),
            },
          ]}
        />
        {scopeTab === "modules" && <ScopeList title={t("licenseAgentModules")} modules={modules} />}
        {scopeTab === "features" && <ScopeList title={t("licenseCoreFeatures")} features={features} />}
      </div>
    </section>
  );
}

function ScopeList({
  features,
  modules,
  title,
}: {
  features?: AuthorizedFeature[];
  modules?: AuthorizedModule[];
  title: string;
}) {
  const { t } = useLocale();
  return (
    <div>
      <h3>{title}</h3>
      {modules?.map((module) => (
        <div className={cx("scope-row", !module.licensed && "locked")} key={module.id}>
          <span>
            <KeyRound size={15} /> {module.name}
          </span>
          <StatusBadge status={formatState(module.state)} label={formatModuleState(module.state, t)} />
        </div>
      ))}
      {features?.map((feature) => (
        <div className={cx("scope-row", !feature.enabled && "locked")} key={feature.id}>
          <span>
            <KeyRound size={15} /> {feature.name}
          </span>
          <StatusBadge
            status={feature.enabled ? "INCLUDED" : "NOT LICENSED"}
            label={feature.enabled ? t("licenseFeatureIncluded") : t("modulesStateNotLicensed")}
          />
        </div>
      ))}
    </div>
  );
}
