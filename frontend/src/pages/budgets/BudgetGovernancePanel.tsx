import { CircleDollarSign, Database, ShieldCheck, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import { PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { BudgetScopeType, BudgetSummaryResponse } from "../../lib/api";
import { formatScope } from "./budgetUtils";

const governanceSteps = [
  { icon: SlidersHorizontal, titleKey: "budgetsGovernancePolicy", bodyKey: "budgetsGovernancePolicyBody" },
  { icon: ShieldCheck, titleKey: "budgetsGovernanceGuard", bodyKey: "budgetsGovernanceGuardBody" },
  { icon: CircleDollarSign, titleKey: "budgetsGovernanceSettle", bodyKey: "budgetsGovernanceSettleBody" },
  { icon: Database, titleKey: "budgetsGovernanceLedger", bodyKey: "budgetsGovernanceLedgerBody" },
];

const supportedScopes: BudgetScopeType[] = ["tenant", "department", "cost_center", "user", "agent", "channel"];

type BudgetGovernanceTab = "chain" | "scope";

interface BudgetGovernancePanelProps {
  loading: boolean;
  summary: BudgetSummaryResponse | null;
}

export function BudgetGovernancePanel({ loading, summary }: BudgetGovernancePanelProps) {
  const { t } = useLocale();
  const [activeTab, setActiveTab] = useState<BudgetGovernanceTab>("chain");
  const stats = [
    { label: t("budgetsHardPolicies"), value: summary?.hard_policy_count ?? 0 },
    { label: t("budgetsSoftPolicies"), value: summary?.soft_policy_count ?? 0 },
    { label: t("budgetsWarnings"), value: summary?.warning_policy_count ?? 0 },
    { label: t("budgetsExceeded"), value: summary?.exceeded_policy_count ?? 0 },
  ];

  return (
    <section className="panel budget-governance-panel">
      <div className="panel-heading">
        <div>
          <h2>{t("budgetsGovernanceTitle")}</h2>
          <p>{t("budgetsGovernanceSubtitle")}</p>
        </div>
        <span className="coverage-note">{loading ? t("budgetsLoading") : t("budgetsPreCallEnforcement")}</span>
      </div>
      <div className="nested-workspace budget-governance-workspace">
        <PageTabs
          active={activeTab}
          onChange={setActiveTab}
          tabs={[
            {
              id: "chain",
              label: t("budgetsGovernanceTabChain"),
              description: t("budgetsGovernanceTabChainDesc"),
            },
            {
              id: "scope",
              label: t("budgetsGovernanceTabScope"),
              description: t("budgetsGovernanceTabScopeDesc"),
            },
          ]}
        />
        {activeTab === "chain" && (
          <div className="budget-governance-grid">
            {governanceSteps.map((step) => {
              const Icon = step.icon;
              return (
                <article className="governance-step-card" key={step.titleKey}>
                  <Icon size={20} />
                  <h3>{t(step.titleKey)}</h3>
                  <p>{t(step.bodyKey)}</p>
                </article>
              );
            })}
          </div>
        )}
        {activeTab === "scope" && (
          <div className="budget-governance-scope-panel">
            <div>
              <span>{t("budgetsGovernanceSupportedScopes")}</span>
              <div className="scope-chip-row">
                {supportedScopes.map((scope) => (
                  <span key={scope}>{formatScope(scope, t)}</span>
                ))}
              </div>
            </div>
            <div>
              <span>{t("budgetsGovernancePolicyStatus")}</span>
              <div className="budget-governance-stats">
                {stats.map((stat) => (
                  <span key={stat.label}>
                    <strong>{stat.value}</strong>
                    {stat.label}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
