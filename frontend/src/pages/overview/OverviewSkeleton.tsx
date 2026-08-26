import { Skeleton } from "../../components/app-ui";

/**
 * Loading placeholder for OverviewPage. Mirrors the real content shape:
 * 4 KPI cards, a chart panel, and a table panel. Layout is responsive
 * (4 columns desktop / 2 tablet / 1 mobile) via the overview-skeleton CSS.
 */
export function OverviewSkeleton() {
  return (
    <div className="overview-skeleton" role="status" aria-live="polite" aria-busy="true">
      <div className="kpi-grid-skeleton">
        {[0, 1, 2, 3].map((index) => (
          <div className="kpi-card-skeleton" key={index}>
            <Skeleton width="60%" height={12} />
            <Skeleton width="40%" height={28} />
            <Skeleton width="80%" height={10} />
          </div>
        ))}
      </div>
      <div className="chart-skeleton">
        <Skeleton width="30%" height={16} />
        <Skeleton height={200} />
      </div>
      <div className="table-skeleton">
        <Skeleton width="20%" height={16} />
        <Skeleton height={32} />
        <Skeleton height={32} />
        <Skeleton height={32} />
        <Skeleton height={32} />
      </div>
    </div>
  );
}
