import { useLocale } from "../../i18n-context";
import type { DepartmentUsageItem } from "../../lib/api";
import { DepartmentCostPanel } from "./DepartmentCostPanel";
import { OverviewRankWorkspace } from "./OverviewRankWorkspace";
import type { UsageRankItem } from "./UsageRankPanel";

export function OverviewUsagePanel({
  agentRankItems,
  departmentUsage,
  totalTokens,
  userRankItems,
}: {
  agentRankItems: UsageRankItem[];
  departmentUsage: DepartmentUsageItem[];
  totalTokens: number;
  userRankItems: UsageRankItem[];
}) {
  const { t } = useLocale();

  return (
    <div className="overview-usage-panel">
      <DepartmentCostPanel departmentUsage={departmentUsage} totalTokens={totalTokens} />
      <section className="overview-usage-section">
        <header className="overview-usage-section-head">
          <h2>{t("overviewTabPeople")}</h2>
          <p>{t("overviewTabPeopleDesc")}</p>
        </header>
        <OverviewRankWorkspace items={userRankItems} kind="people" totalTokens={totalTokens} />
      </section>
      <section className="overview-usage-section">
        <header className="overview-usage-section-head">
          <h2>{t("overviewTabAgents")}</h2>
          <p>{t("overviewTabAgentsDesc")}</p>
        </header>
        <OverviewRankWorkspace items={agentRankItems} kind="agents" totalTokens={totalTokens} />
      </section>
    </div>
  );
}
