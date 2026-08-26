import { useLocale } from "../../i18n-context";
import { type UsageRankItem, UsageRankPanel } from "./UsageRankPanel";

type RankKind = "people" | "agents";

const rankCopyKeys = {
  agents: {
    emptyMessage: "overviewNoAgentUsageMessage",
    emptyTitle: "overviewNoAgentUsageTitle",
    subtitle: "overviewAgentUsageAlt",
    title: "overviewAgentUsage",
  },
  people: {
    emptyMessage: "overviewNoUserUsageMessage",
    emptyTitle: "overviewNoUserUsageTitle",
    subtitle: "overviewUserUsageAlt",
    title: "overviewUserUsage",
  },
} satisfies Record<RankKind, Record<"emptyMessage" | "emptyTitle" | "subtitle" | "title", string>>;

export function OverviewRankWorkspace({
  items,
  kind,
  totalTokens,
}: {
  items: UsageRankItem[];
  kind: RankKind;
  totalTokens: number;
}) {
  const { t } = useLocale();
  const copy = rankCopyKeys[kind];

  return (
    <div className="grid one usage-rank-grid">
      <UsageRankPanel
        emptyMessage={t(copy.emptyMessage)}
        emptyTitle={t(copy.emptyTitle)}
        items={items}
        subtitle={t(copy.subtitle)}
        title={t(copy.title)}
        totalTokens={totalTokens}
      />
    </div>
  );
}
