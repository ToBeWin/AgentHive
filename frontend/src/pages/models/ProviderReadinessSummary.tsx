import { CheckCircle2, CircleAlert, CircleX, LoaderCircle, type LucideIcon } from "lucide-react";
import { cx, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { LLMConnectionTestResponse, LLMProviderResponse } from "../../lib/api";

export type ProviderReadinessKind = "configured" | "failure" | "not-configured" | "success" | "testing" | "unavailable";

interface ProviderReadinessSummaryProps {
  compact?: boolean;
  lastTestResult?: LLMConnectionTestResponse | null;
  provider: LLMProviderResponse;
  testing?: boolean;
}

export function ProviderReadinessSummary({
  compact = false,
  lastTestResult = null,
  provider,
  testing = false,
}: ProviderReadinessSummaryProps) {
  const { t } = useLocale();
  const readiness = resolveProviderReadiness({ lastTestResult, provider, testing });
  const Icon = readiness.icon;
  const detail =
    readiness.detailKey === "modelsProviderReadinessSuccessDetail"
      ? t(readiness.detailKey)
          .replace("{{provider}}", provider.name)
          .replace("{{latency}}", String(lastTestResult?.latency_ms ?? 0))
      : t(readiness.detailKey);

  return (
    <div
      aria-live={readiness.kind === "testing" ? "polite" : undefined}
      className={cx("provider-readiness", `provider-readiness-${readiness.kind}`, compact && "compact")}
    >
      <span className="provider-readiness-icon" aria-hidden="true">
        <Icon
          className={readiness.kind === "testing" ? "provider-readiness-spinner" : undefined}
          size={compact ? 14 : 17}
        />
      </span>
      <span className="provider-readiness-copy">
        {compact ? (
          <small>{detail}</small>
        ) : (
          <>
            <strong>{t(readiness.labelKey)}</strong>
            <small>{detail}</small>
          </>
        )}
      </span>
      {!compact && <StatusBadge label={t(readiness.labelKey)} status={readiness.badgeStatus} />}
    </div>
  );
}

export function resolveProviderReadiness({
  lastTestResult,
  provider,
  testing,
}: {
  lastTestResult?: LLMConnectionTestResponse | null;
  provider: LLMProviderResponse;
  testing?: boolean;
}): {
  badgeStatus: string;
  detailKey: string;
  icon: LucideIcon;
  kind: ProviderReadinessKind;
  labelKey: string;
} {
  if (testing) {
    return {
      badgeStatus: "pending",
      detailKey: "modelsProviderReadinessTestingDetail",
      icon: LoaderCircle,
      kind: "testing",
      labelKey: "modelsProviderReadinessTesting",
    };
  }

  if (lastTestResult?.provider_key === provider.provider_key) {
    return lastTestResult.ok
      ? {
          badgeStatus: "active",
          detailKey: "modelsProviderReadinessSuccessDetail",
          icon: CheckCircle2,
          kind: "success",
          labelKey: "modelsProviderReadinessSuccess",
        }
      : {
          badgeStatus: "error",
          detailKey: "modelsProviderReadinessFailureDetail",
          icon: CircleX,
          kind: "failure",
          labelKey: "modelsProviderReadinessFailure",
        };
  }

  if (provider.status === "inactive") {
    return {
      badgeStatus: "blocked",
      detailKey: "modelsProviderReadinessUnavailableDetail",
      icon: CircleAlert,
      kind: "unavailable",
      labelKey: "modelsProviderReadinessUnavailable",
    };
  }

  if (!provider.credential_configured) {
    return {
      badgeStatus: "not-configured",
      detailKey: "modelsProviderReadinessNotConfiguredDetail",
      icon: CircleAlert,
      kind: "not-configured",
      labelKey: "modelsProviderStatusNotConfigured",
    };
  }

  if (provider.status !== "active") {
    return {
      badgeStatus: "blocked",
      detailKey: "modelsProviderReadinessUnavailableDetail",
      icon: CircleAlert,
      kind: "unavailable",
      labelKey: "modelsProviderReadinessUnavailable",
    };
  }

  return {
    badgeStatus: "configured",
    detailKey: "modelsProviderReadinessConfiguredDetail",
    icon: CheckCircle2,
    kind: "configured",
    labelKey: "modelsProviderStatusConfigured",
  };
}
