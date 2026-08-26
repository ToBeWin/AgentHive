import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { cx } from "./app-ui";

export type SortDirection = "asc" | "desc" | null;

export function SortableTh({
  label,
  sortKey,
  currentSortKey,
  currentDirection,
  onSort,
  className,
}: {
  label: string;
  sortKey: string;
  currentSortKey?: string;
  currentDirection?: SortDirection;
  onSort?: (key: string, direction: SortDirection) => void;
  className?: string;
}) {
  const isActive = currentSortKey === sortKey;
  const nextDirection: SortDirection = isActive
    ? currentDirection === "asc"
      ? "desc"
      : currentDirection === "desc"
        ? null
        : "asc"
    : "asc";

  const ariaSort: "ascending" | "descending" | "none" = isActive
    ? currentDirection === "asc"
      ? "ascending"
      : currentDirection === "desc"
        ? "descending"
        : "none"
    : "none";

  return (
    <th className={cx("sortable-th", isActive && "active", className)} aria-sort={ariaSort}>
      {onSort ? (
        <button type="button" className="sortable-th-button" onClick={() => onSort(sortKey, nextDirection)}>
          <span>{label}</span>
          {isActive && currentDirection === "asc" && <ArrowUp size={12} aria-hidden="true" />}
          {isActive && currentDirection === "desc" && <ArrowDown size={12} aria-hidden="true" />}
          {(!isActive || !currentDirection) && <ArrowUpDown size={12} className="sort-inactive" aria-hidden="true" />}
        </button>
      ) : (
        <span>{label}</span>
      )}
    </th>
  );
}

export function sortItems<T>(
  items: T[],
  sortKey: string,
  direction: SortDirection,
  getSortValue: (item: T, key: string) => string | number | Date,
): T[] {
  if (!direction) return items;
  return [...items].sort((a, b) => {
    const aVal = getSortValue(a, sortKey);
    const bVal = getSortValue(b, sortKey);
    if (aVal < bVal) return direction === "asc" ? -1 : 1;
    if (aVal > bVal) return direction === "asc" ? 1 : -1;
    return 0;
  });
}
