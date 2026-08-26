import { useLocale } from "../../i18n-context";
import type { DailyUsageItem } from "../../lib/api";

export function TokenTrendPanel({ dailyUsage }: { dailyUsage: DailyUsageItem[] }) {
  const { t } = useLocale();
  const maxDailyTokens = Math.max(1, ...dailyUsage.map((item) => item.tokens));
  const trendPoints = dailyUsage.length
    ? dailyUsage
        .map((item, index) => {
          const x = dailyUsage.length === 1 ? 380 : (index / (dailyUsage.length - 1)) * 760;
          const y = 230 - (item.tokens / maxDailyTokens) * 180;
          return `${x},${y}`;
        })
        .join(" ")
    : "0,220 760,220";

  return (
    <div className="grid one">
      <section className="panel">
        <div className="panel-title">
          <h2>
            {t("overviewTokenTrend")} <span>{t("overviewTokenTrendAlt")}</span>
          </h2>
          <div className="legend">
            <i /> {t("overviewInput")} <i className="muted" /> {t("overviewOutput")}
          </div>
        </div>
        <div className="chart-line">
          <svg viewBox="0 0 760 260" role="img" aria-labelledby="token-chart-title">
            <title id="token-chart-title">{t("overviewTokenChartTitle")}</title>
            <polyline points={trendPoints} fill="none" stroke="#008378" strokeWidth="3" />
          </svg>
          <div className="axis-labels">
            {dailyUsage.length ? (
              dailyUsage.map((item) => <span key={item.date}>{item.date.slice(5) || item.date}</span>)
            ) : (
              <span>{t("overviewNoData")}</span>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
