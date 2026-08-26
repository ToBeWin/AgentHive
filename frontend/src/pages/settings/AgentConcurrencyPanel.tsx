import { Activity, Gauge, ShieldCheck, Users } from "lucide-react";
import { Panel, StatusBadge } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { SystemComponentReport, SystemHealthReport } from "../../lib/api";
import { componentStatusLabel, formatDetailValue, localizedRemediationText } from "./settingsUtils";

interface ConcurrencyMetric {
  icon: typeof Gauge;
  labelKey: string;
  value: string;
}

export function AgentConcurrencyPanel({ report }: { report: SystemHealthReport | null }) {
  const { t } = useLocale();
  const component = report?.components.agent_concurrency ?? null;
  const details = component?.details ?? {};
  const enabled = details.enabled === true;
  const metrics = concurrencyMetrics(details);
  const remediation = localizedRemediationText(component?.remediation, t);

  return (
    <Panel
      title={t("settingsAgentConcurrencyTitle")}
      subtitle={t("settingsAgentConcurrencyHelp")}
      actions={
        component ? (
          <StatusBadge status={component.status} label={componentStatusLabel(component.status, t)} />
        ) : (
          <StatusBadge status="not_configured" label={t("settingsComponentStatusNotConfigured")} />
        )
      }
      className="agent-concurrency-panel"
    >
      <div className="agent-concurrency-summary">
        <div className="agent-concurrency-state">
          <ShieldCheck size={20} />
          <div>
            <strong>{enabled ? t("settingsAgentConcurrencyEnabled") : t("settingsAgentConcurrencyDisabled")}</strong>
            <span>{component?.message ?? t("settingsAgentConcurrencyNoData")}</span>
          </div>
        </div>
        {remediation && (
          <p className="settings-remediation">
            <strong>{t("settingsRemediation")}</strong>
            {remediation}
          </p>
        )}
      </div>

      <div className="agent-concurrency-metrics">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <div className="agent-concurrency-metric" key={metric.labelKey}>
              <Icon size={18} />
              <span>{t(metric.labelKey)}</span>
              <strong>{metric.value}</strong>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function concurrencyMetrics(details: NonNullable<SystemComponentReport["details"]>): ConcurrencyMetric[] {
  return [
    {
      icon: Gauge,
      labelKey: "settingsDetailTenantLimit",
      value: formatDetailValue(details.tenant_limit),
    },
    {
      icon: Users,
      labelKey: "settingsDetailUserLimit",
      value: formatDetailValue(details.user_limit),
    },
    {
      icon: ShieldCheck,
      labelKey: "settingsDetailAgentLimit",
      value: formatDetailValue(details.agent_limit),
    },
    {
      icon: Activity,
      labelKey: "settingsDetailActiveSlotCount",
      value: formatDetailValue(details.active_slot_count),
    },
  ];
}
