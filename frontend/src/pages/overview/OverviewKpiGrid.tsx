import { type LucideIcon, TrendingDown, TrendingUp } from "lucide-react";
import { cx } from "../../components/app-ui";
import { Sparkline } from "../../components/Sparkline";

export interface OverviewKpiCard {
  label: string;
  value: string;
  delta: string;
  tone: "bad" | "good" | "neutral";
  icon: LucideIcon;
  /** Optional 30/90-day trend used to render the sparkline + delta arrow. */
  trend?: number[];
  /** Optional accessible label for the sparkline (defaults to `${label} trend`). */
  trendAriaLabel?: string;
}

type TrendInfo = { direction: "up" | "down" | "flat"; pct: number };

function computeTrend(data: number[] | undefined): TrendInfo | null {
  if (!data || data.length < 2) {
    return null;
  }
  const first = data[0];
  const last = data[data.length - 1];
  if (first === 0) {
    if (last === 0) {
      return { direction: "flat", pct: 0 };
    }
    return null;
  }
  const pct = ((last - first) / Math.abs(first)) * 100;
  if (Math.abs(pct) < 0.05) {
    return { direction: "flat", pct: 0 };
  }
  return { direction: pct > 0 ? "up" : "down", pct };
}

function formatTrendPct(pct: number): string {
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

export function OverviewKpiGrid({ cards }: { cards: OverviewKpiCard[] }) {
  return (
    <div className="kpi-grid">
      {cards.map((kpi) => {
        const Icon = kpi.icon;
        const trendInfo = computeTrend(kpi.trend);
        const showSparkline = Boolean(kpi.trend && kpi.trend.length > 1);
        const ariaLabel = kpi.trendAriaLabel ?? `${kpi.label} trend`;
        return (
          <article className="metric-card" key={kpi.label}>
            <div className="metric-card-info">
              <div className="metric-label">
                <span>{kpi.label}</span>
                <Icon size={20} />
              </div>
              <strong className="metric-value">{kpi.value}</strong>
              <div className="metric-delta-row">
                {trendInfo && (
                  <span
                    className={cx("metric-trend-badge", trendInfo.direction)}
                    role="img"
                    aria-label={`${trendInfo.direction} ${formatTrendPct(trendInfo.pct)}`}
                  >
                    {trendInfo.direction === "up" ? (
                      <TrendingUp size={12} aria-hidden="true" />
                    ) : trendInfo.direction === "down" ? (
                      <TrendingDown size={12} aria-hidden="true" />
                    ) : null}
                    {formatTrendPct(trendInfo.pct)}
                  </span>
                )}
                <span className={cx("metric-delta-text", kpi.tone === "bad" ? "bad" : "good")}>{kpi.delta}</span>
              </div>
            </div>
            {showSparkline && (
              <div className="metric-card-trend">
                <Sparkline data={kpi.trend ?? []} ariaLabel={ariaLabel} />
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}
