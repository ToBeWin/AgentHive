import { ChevronLeft, ChevronRight } from "lucide-react";
import { useLocale } from "../i18n-context";
import { cx } from "./app-ui";

export const DEFAULT_PAGE_SIZE = 20;
export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

export interface PaginationState {
  page: number;
  pageSize: number;
}

export function paginate<T>(items: T[], { page, pageSize }: PaginationState): T[] {
  const start = (page - 1) * pageSize;
  return items.slice(start, start + pageSize);
}

export function TablePagination({
  total,
  page,
  pageSize,
  pageSizeOptions = PAGE_SIZE_OPTIONS,
  onPageChange,
  onPageSizeChange,
  className,
}: {
  total: number;
  page: number;
  pageSize: number;
  pageSizeOptions?: number[];
  onPageChange: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
  className?: string;
}) {
  const { t } = useLocale();
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const currentPage = Math.min(Math.max(1, page), totalPages);
  const start = total === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const end = Math.min(currentPage * pageSize, total);

  if (total === 0) return null;

  return (
    <nav className={cx("table-pagination", className)} aria-label={t("paginationNav")}>
      <span className="pagination-info">
        {t("paginationRange")
          .replace("{{start}}", String(start))
          .replace("{{end}}", String(end))
          .replace("{{total}}", String(total))}
      </span>
      <div className="pagination-controls">
        <button
          type="button"
          className="pagination-btn"
          disabled={currentPage <= 1}
          onClick={() => onPageChange(currentPage - 1)}
          aria-label={t("paginationPrevious")}
        >
          <ChevronLeft size={14} aria-hidden="true" />
        </button>
        <span className="pagination-page">
          {t("paginationPage").replace("{{page}}", String(currentPage)).replace("{{pages}}", String(totalPages))}
        </span>
        <button
          type="button"
          className="pagination-btn"
          disabled={currentPage >= totalPages}
          onClick={() => onPageChange(currentPage + 1)}
          aria-label={t("paginationNext")}
        >
          <ChevronRight size={14} aria-hidden="true" />
        </button>
      </div>
      {onPageSizeChange && (
        <select
          className="pagination-page-size"
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          aria-label={t("paginationPageSize")}
        >
          {pageSizeOptions.map((size) => (
            <option key={size} value={size}>
              {t("paginationPageSizeOption").replace("{{size}}", String(size))}
            </option>
          ))}
        </select>
      )}
    </nav>
  );
}
