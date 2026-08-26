import { PageTabs } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import type { DailyUsageItem, DepartmentUsageItem, ModelUsageItem } from "../../lib/api";
import { ModelPerformancePanel } from "./ModelPerformancePanel";
import { OverviewUsagePanel } from "./OverviewUsagePanel";
import type { OverviewAnalysisTab } from "./overviewAnalysisTypes";
import { TokenTrendPanel } from "./TokenTrendPanel";
import type { UsageRankItem } from "./UsageRankPanel";

export type { OverviewAnalysisTab } from "./overviewAnalysisTypes";

export function OverviewAnalysisWorkspace({
  agentRankItems,
  analysisTab,
  dailyUsage,
  departmentUsage,
  modelUsage,
  onAnalysisTabChange,
  onOpenModelCoverage,
  totalTokens,
  userRankItems,
}: {
  agentRankItems: UsageRankItem[];
  analysisTab: OverviewAnalysisTab;
  dailyUsage: DailyUsageItem[];
  departmentUsage: DepartmentUsageItem[];
  modelUsage: ModelUsageItem[];
  onAnalysisTabChange: (tab: OverviewAnalysisTab) => void;
  onOpenModelCoverage: () => void;
  totalTokens: number;
  userRankItems: UsageRankItem[];
}) {
  const { t } = useLocale();

  return (
    <section className="overview-analysis-workspace">
      <PageTabs
        active={analysisTab}
        onChange={onAnalysisTabChange}
        tabs={[
          { id: "trend", label: t("overviewTabTrend"), description: t("overviewTabTrendDesc") },
          { id: "usage", label: t("overviewTabUsage"), description: t("overviewTabUsageDesc") },
          { id: "models", label: t("overviewTabModels"), description: t("overviewTabModelsDesc") },
        ]}
      />
      {analysisTab === "trend" && <TokenTrendPanel dailyUsage={dailyUsage} />}
      {analysisTab === "usage" && (
        <OverviewUsagePanel
          agentRankItems={agentRankItems}
          departmentUsage={departmentUsage}
          totalTokens={totalTokens}
          userRankItems={userRankItems}
        />
      )}
      {analysisTab === "models" && (
        <ModelPerformancePanel modelUsage={modelUsage} onOpenModelCoverage={onOpenModelCoverage} />
      )}
    </section>
  );
}
