import { ApiNotice } from "../../components/app-ui";
import { useLocale } from "../../i18n-context";
import { formatCurrency, formatNumber } from "../../lib/formatters";

export interface UsageRankItem {
  id: string;
  title: string;
  subtitle: string;
  tokens: number;
  cost_usd: number;
  requests: number;
}

interface UsageRankPanelProps {
  title: string;
  subtitle: string;
  emptyTitle: string;
  emptyMessage: string;
  totalTokens: number;
  items: UsageRankItem[];
}

export function UsageRankPanel({ title, subtitle, emptyTitle, emptyMessage, totalTokens, items }: UsageRankPanelProps) {
  const { locale } = useLocale();
  return (
    <section className="panel usage-rank-panel">
      <div className="panel-title compact">
        <h2>
          {title} <span>{subtitle}</span>
        </h2>
      </div>
      {items.length === 0 ? (
        <ApiNotice title={emptyTitle} message={emptyMessage} />
      ) : (
        <div className="usage-rank-list">
          {items.slice(0, 6).map((item, index) => (
            <div className="usage-rank-row" key={item.id}>
              <div className="usage-rank-index">{index + 1}</div>
              <div className="usage-rank-main">
                <div>
                  <strong>{item.title}</strong>
                  <span>{item.subtitle}</span>
                </div>
                <div className="bar-track">
                  <i style={{ width: `${Math.min(100, (item.tokens / Math.max(1, totalTokens)) * 100)}%` }} />
                </div>
              </div>
              <div className="usage-rank-metrics">
                <code>{formatCurrency(item.cost_usd)}</code>
                <span>{formatNumber(item.requests, {}, locale)} req</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
