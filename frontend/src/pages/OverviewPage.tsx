import { BarChart3, Boxes, Brain, Calendar, Download, Scale } from "lucide-react";
import { useMemo, useState } from "react";
import { ApiNotice, Button, PageHeader } from "../components/app-ui";
import type { PageId, WorkspaceId } from "../data";
import { useAnalyticsOverview } from "../hooks/useAdminData";
import { useLocale } from "../i18n-context";
import { downloadTextFile } from "../lib/download";
import { formatCompactCurrency, formatNumber } from "../lib/formatters";
import { type OverviewAnalysisTab, OverviewAnalysisWorkspace } from "./overview/OverviewAnalysisWorkspace";
import { type OverviewKpiCard, OverviewKpiGrid } from "./overview/OverviewKpiGrid";
import { OverviewQuickActions } from "./overview/OverviewQuickActions";
import { OverviewSkeleton } from "./overview/OverviewSkeleton";
import type { UsageRankItem } from "./overview/UsageRankPanel";

type PeriodKey = "7d" | "30d" | "90d";

const MODEL_TAB_REQUEST_KEY = "agenthive.models.default_tab";

const periodDays: Record<PeriodKey, number> = {
  "7d": 7,
  "30d": 30,
  "90d": 90,
};

const periodLabelKeys: Record<PeriodKey, string> = {
  "7d": "overviewLast7Days",
  "30d": "overviewLast30Days",
  "90d": "overviewLast90Days",
};

function escapeCsvCell(value: string | number | null | undefined) {
  const text = value === null || value === undefined ? "" : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

function makeOverviewCsv({
  generatedAt,
  totals,
  departmentUsage,
  modelUsage,
  userUsage,
  agentUsage,
}: {
  generatedAt: string;
  totals: {
    total_requests: number;
    total_tokens: number;
    total_cost_usd: number;
    success_rate: number;
  };
  departmentUsage: Array<{ department_name: string; tokens: number; cost_usd: number; requests: number }>;
  modelUsage: Array<{ model_key: string; tokens: number; cost_usd: number; requests: number }>;
  userUsage: Array<{ user_name: string; tokens: number; cost_usd: number; requests: number }>;
  agentUsage: Array<{ agent_name: string; tokens: number; cost_usd: number; requests: number }>;
}) {
  const rows: Array<Array<string | number>> = [
    ["section", "name", "requests", "tokens", "cost_usd", "extra"],
    ["generated_at", generatedAt, "", "", "", ""],
    ["total", "all", totals.total_requests, totals.total_tokens, totals.total_cost_usd, totals.success_rate],
    ...departmentUsage.map((item) => [
      "department",
      item.department_name,
      item.requests,
      item.tokens,
      item.cost_usd,
      "",
    ]),
    ...modelUsage.map((item) => ["model", item.model_key, item.requests, item.tokens, item.cost_usd, ""]),
    ...userUsage.map((item) => ["user", item.user_name, item.requests, item.tokens, item.cost_usd, ""]),
    ...agentUsage.map((item) => ["agent", item.agent_name, item.requests, item.tokens, item.cost_usd, ""]),
  ];

  return `\uFEFF${rows.map((row) => row.map(escapeCsvCell).join(",")).join("\n")}\n`;
}

export function OverviewPage({
  activeWorkspace = "admin",
  isPrototype = false,
  onNavigate,
}: {
  activeWorkspace?: WorkspaceId;
  isPrototype?: boolean;
  onNavigate?: (page: PageId) => void;
}) {
  const analytics = useAnalyticsOverview({ fallbackOnError: isPrototype });
  const { locale, t } = useLocale();
  const [periodKey, setPeriodKey] = useState<PeriodKey>("30d");
  const [analysisTab, setAnalysisTab] = useState<OverviewAnalysisTab>("trend");
  const [exportStatus, setExportStatus] = useState("");
  const data = analytics.data;
  const totals = data?.totals;
  const dailyUsage = data?.daily_usage ?? [];
  const visibleDailyUsage = useMemo(
    () => dailyUsage.slice(-Math.min(dailyUsage.length, periodDays[periodKey])),
    [dailyUsage, periodKey],
  );
  const departmentUsage = data?.department_usage ?? [];
  const modelUsage = data?.model_usage ?? [];
  const userUsage = data?.user_usage ?? [];
  const agentUsage = data?.agent_usage ?? [];
  const totalCost = totals?.total_cost_usd ?? 0;
  const totalTokens = totals?.total_tokens ?? 0;
  const totalRequests = totals?.total_requests ?? 0;
  const successRate = totals?.success_rate ?? 0;
  // Sparkline trends always reflect the full available daily series so the
  // mini chart remains meaningful even when the user picks a 7d window above.
  const requestsTrend = useMemo(() => dailyUsage.map((d) => d.requests), [dailyUsage]);
  const tokensTrend = useMemo(() => dailyUsage.map((d) => d.tokens), [dailyUsage]);
  const costTrend = useMemo(() => dailyUsage.map((d) => d.cost_usd), [dailyUsage]);
  const userRankItems: UsageRankItem[] = userUsage.map((item) => ({
    id: item.user_id ?? item.user_name,
    title: item.user_name,
    subtitle: `${formatNumber(item.tokens, {}, locale)} ${t("overviewTokenUnit")}`,
    tokens: item.tokens,
    cost_usd: item.cost_usd,
    requests: item.requests,
  }));
  const agentRankItems: UsageRankItem[] = agentUsage.map((item) => ({
    id: item.agent_id ?? item.agent_name,
    title: item.agent_name,
    subtitle: item.agent_key ?? t("overviewDirectModelCalls"),
    tokens: item.tokens,
    cost_usd: item.cost_usd,
    requests: item.requests,
  }));
  const kpiCards: OverviewKpiCard[] = [
    {
      label: t("overviewTotalRequests"),
      value: formatNumber(totalRequests, {}, locale),
      delta: `${Math.round(successRate * 1000) / 10}% ${t("overviewSuccessRate")}`,
      tone: successRate >= 0.98 || totalRequests === 0 ? "good" : "bad",
      icon: BarChart3,
      trend: requestsTrend,
      trendAriaLabel: `${t("overviewTotalRequestsAlt")} ${t("overviewSparklineTrend")}`,
    },
    {
      label: t("overviewTokenUsage"),
      value: formatNumber(totalTokens, { notation: "compact" }, locale),
      delta: t("overviewTokenDelta"),
      tone: "neutral",
      icon: Boxes,
      trend: tokensTrend,
      trendAriaLabel: `${t("overviewTokenUsageAlt")} ${t("overviewSparklineTrend")}`,
    },
    {
      label: t("overviewModelCost"),
      value: formatCompactCurrency(totalCost, "USD", locale),
      delta: t("overviewModelCostDelta"),
      tone: "neutral",
      icon: Scale,
      trend: costTrend,
      trendAriaLabel: `${t("overviewModelCostAlt")} ${t("overviewSparklineTrend")}`,
    },
    {
      label: t("overviewActiveModels"),
      value: `${modelUsage.length}`,
      delta: t("overviewActiveModelsDelta"),
      tone: "good",
      icon: Brain,
    },
  ];
  const exportOverviewReport = () => {
    if (!data) {
      return;
    }
    const csv = makeOverviewCsv({
      generatedAt: data.generated_at,
      totals: data.totals,
      departmentUsage,
      modelUsage,
      userUsage,
      agentUsage,
    });
    const datePart = new Date().toISOString().slice(0, 10);
    downloadTextFile(csv, `agenthive-overview-${datePart}.csv`, "text/csv;charset=utf-8");
    setExportStatus(t("overviewExportReady"));
    window.setTimeout(() => setExportStatus(""), 2500);
  };
  const openModelCoverage = () => {
    window.sessionStorage.setItem(MODEL_TAB_REQUEST_KEY, "coverage");
    onNavigate?.("models");
  };

  return (
    <section className="page overview-page">
      <PageHeader
        title={t("overviewTitle")}
        subtitle={t("overviewSubtitle")}
        actions={
          <>
            <label className="period-select-wrapper">
              <Calendar size={16} aria-hidden />
              <select
                className="period-select"
                value={periodKey}
                onChange={(event) => setPeriodKey(event.target.value as PeriodKey)}
                aria-label={t("overviewPeriodLabel")}
              >
                {(Object.keys(periodLabelKeys) as PeriodKey[]).map((key) => (
                  <option key={key} value={key}>
                    {t(periodLabelKeys[key])}
                  </option>
                ))}
              </select>
            </label>
            <Button variant="primary" onClick={exportOverviewReport} disabled={!data}>
              <Download size={16} /> {t("exportReport")}
            </Button>
            {exportStatus && (
              <span className="action-feedback" role="status">
                {exportStatus}
              </span>
            )}
          </>
        }
      />
      {analytics.loading && <OverviewSkeleton />}
      {analytics.error && !analytics.loading && (
        <ApiNotice
          title={t("overviewLoadErrorTitle")}
          message={analytics.error}
          action={<Button onClick={analytics.refetch}>{t("commonRetry")}</Button>}
        />
      )}
      {!analytics.loading && !analytics.error && (
        <>
          <OverviewKpiGrid cards={kpiCards} />
          <OverviewQuickActions activeWorkspace={activeWorkspace} onNavigate={onNavigate} />
          <OverviewAnalysisWorkspace
            agentRankItems={agentRankItems}
            analysisTab={analysisTab}
            dailyUsage={visibleDailyUsage}
            departmentUsage={departmentUsage}
            modelUsage={modelUsage}
            onAnalysisTabChange={setAnalysisTab}
            onOpenModelCoverage={openModelCoverage}
            totalTokens={totalTokens}
            userRankItems={userRankItems}
          />
        </>
      )}
    </section>
  );
}
