import { CheckCircle2, Database, KeyRound, type LucideIcon, PackageCheck, Server, ShieldCheck } from "lucide-react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { SetupStatusResponse } from "../../lib/api";

type PreflightState = "ready" | "review" | "blocked";

interface PreflightItem {
  icon: LucideIcon;
  label: string;
  detail: string;
  state: PreflightState;
}

interface DeliveryStep {
  icon: LucideIcon;
  title: string;
  detail: string;
  state: "complete" | "next" | "pending";
}

export function SetupPreflightPanel({
  error,
  setupStatus,
}: {
  error: string | null;
  setupStatus: SetupStatusResponse | null;
}) {
  const { t } = useLocale();
  const diagnostics = setupStatus?.diagnostics ?? {};
  const diagnosticStatus = typeof diagnostics.status === "string" ? diagnostics.status : null;
  const diagnosticComponent = typeof diagnostics.component === "string" ? diagnostics.component : null;
  const hasApiStatus = Boolean(setupStatus);
  const apiBlocked = !hasApiStatus && Boolean(error);
  const databaseBlocked = diagnosticStatus === "unhealthy" || apiBlocked;
  const databaseHealthy = diagnosticStatus === "healthy";
  const initialized = setupStatus?.initialized ?? false;
  const setupAvailable = setupStatus?.setup_available ?? false;

  const items: PreflightItem[] = [
    {
      icon: Server,
      label: t("authPreflightApi"),
      detail: hasApiStatus ? t("authPreflightApiReady") : t("authPreflightApiBlocked"),
      state: hasApiStatus ? "ready" : "blocked",
    },
    {
      icon: Database,
      label: t("authPreflightDatabase"),
      detail: databaseDetail({
        apiBlocked,
        databaseHealthy,
        diagnosticComponent,
        t,
      }),
      state: databaseBlocked ? "blocked" : "ready",
    },
    {
      icon: PackageCheck,
      label: t("authPreflightSetupAvailability"),
      detail: setupAvailable
        ? t("authPreflightSetupReady")
        : t(hasApiStatus ? "authPreflightSetupBlocked" : "authPreflightSetupUnknown"),
      state: setupAvailable ? "ready" : "blocked",
    },
    {
      icon: ShieldCheck,
      label: t("authPreflightTenantState"),
      detail: tenantDetail({ hasApiStatus, initialized, setupStatus, t }),
      state: initialized ? "review" : setupAvailable ? "ready" : "blocked",
    },
  ];

  const steps: DeliveryStep[] = [
    {
      icon: CheckCircle2,
      title: t("authDeliveryStepInitialize"),
      detail: t("authDeliveryStepInitializeDetail"),
      state: initialized ? "complete" : "next",
    },
    {
      icon: KeyRound,
      title: t("authDeliveryStepLicense"),
      detail: t("authDeliveryStepLicenseDetail"),
      state: initialized ? "next" : "pending",
    },
    {
      icon: Server,
      title: t("authDeliveryStepModels"),
      detail: t("authDeliveryStepModelsDetail"),
      state: "pending",
    },
    {
      icon: Database,
      title: t("authDeliveryStepStorage"),
      detail: t("authDeliveryStepStorageDetail"),
      state: "pending",
    },
    {
      icon: PackageCheck,
      title: t("authDeliveryStepAgents"),
      detail: t("authDeliveryStepAgentsDetail"),
      state: "pending",
    },
    {
      icon: ShieldCheck,
      title: t("authDeliveryStepDiagnostics"),
      detail: t("authDeliveryStepDiagnosticsDetail"),
      state: "pending",
    },
  ];

  return (
    <section className="setup-preflight" aria-label={t("authPreflightTitle")}>
      <div className="setup-preflight-heading">
        <div>
          <h3>{t("authPreflightTitle")}</h3>
          <p>{t("authPreflightSubtitle")}</p>
        </div>
        <StatusBadge
          status={overallState(items)}
          label={t(overallState(items) === "healthy" ? "authPreflightReady" : "authPreflightBlocked")}
        />
      </div>

      <div className="setup-preflight-grid">
        {items.map((item) => (
          <PreflightCard key={item.label} item={item} />
        ))}
      </div>

      <div className="setup-delivery-plan">
        <h3>{t("authDeliveryPlanTitle")}</h3>
        <ol>
          {steps.map((step) => (
            <li key={step.title} className={cx("setup-delivery-step", `setup-delivery-step-${step.state}`)}>
              <span>
                <step.icon size={16} />
              </span>
              <div>
                <strong>{step.title}</strong>
                <p>{step.detail}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>

      {apiBlocked && <p className="setup-prototype-hint">{t("authPreflightPrototypeHint")}</p>}
    </section>
  );
}

function PreflightCard({ item }: { item: PreflightItem }) {
  const { t } = useLocale();
  return (
    <article className={cx("setup-preflight-card", `setup-preflight-card-${item.state}`)}>
      <div>
        <item.icon size={17} />
        <strong>{item.label}</strong>
      </div>
      <p>{item.detail}</p>
      <StatusBadge status={statusForState(item.state)} label={t(labelForState(item.state))} />
    </article>
  );
}

function overallState(items: PreflightItem[]) {
  return items.some((item) => item.state === "blocked") ? "blocked" : "healthy";
}

function statusForState(state: PreflightState) {
  if (state === "ready") {
    return "healthy";
  }
  if (state === "review") {
    return "degraded";
  }
  return "blocked";
}

function labelForState(state: PreflightState) {
  if (state === "ready") {
    return "authPreflightReady";
  }
  if (state === "review") {
    return "authPreflightReview";
  }
  return "authPreflightBlocked";
}

function databaseDetail({
  apiBlocked,
  databaseHealthy,
  diagnosticComponent,
  t,
}: {
  apiBlocked: boolean;
  databaseHealthy: boolean;
  diagnosticComponent: string | null;
  t: (key: string) => string;
}) {
  if (databaseHealthy) {
    return t("authPreflightDatabaseReady");
  }
  if (apiBlocked) {
    return t("authPreflightDatabaseUnknown");
  }
  if (diagnosticComponent === "database") {
    return t("authPreflightDatabaseBlocked");
  }
  return t("authPreflightDatabaseBlocked");
}

function tenantDetail({
  hasApiStatus,
  initialized,
  setupStatus,
  t,
}: {
  hasApiStatus: boolean;
  initialized: boolean;
  setupStatus: SetupStatusResponse | null;
  t: (key: string) => string;
}) {
  if (!hasApiStatus) {
    return t("authPreflightTenantUnknownDetail");
  }
  if (initialized) {
    return t("authPreflightInitializedDetail");
  }
  return `${t("authPreflightNotInitializedDetail")} ${t("authPreflightTenantCount")}: ${setupStatus?.tenant_count ?? 0}`;
}
