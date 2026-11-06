import type { PageContext } from "@/core/api/types";
import { Button } from "./Button";
import { Select } from "./Select";

const PAGE_SIZES = [10, 20, 50, 100].map((size) => ({ value: String(size), label: `${size} / page` }));

export function Pagination({ pageContext, onPageChange, onPerPageChange, disabled }: {
  pageContext: PageContext | undefined;
  onPageChange: (page: number) => void;
  onPerPageChange: (perPage: number) => void;
  disabled?: boolean;
}) {
  // nothing to page through: an empty list shows its own empty state instead
  if (!pageContext || (pageContext.total_records === 0 && pageContext.page <= 1)) return null;
  const { page, per_page, total_records, total_is_exact, total_pages, has_more_page } = pageContext;
  const first = total_records === 0 ? 0 : (page - 1) * per_page + 1;
  const last = Math.min(page * per_page, total_records);
  const maxPage = Math.floor(10_000 / per_page); // the API does not page beyond 10,000 records

  return (
    <div className="flex flex-col gap-3 border-t border-slate-100 px-4 py-3 text-sm text-slate-600 sm:flex-row sm:items-center sm:justify-between">
      <p>
        {total_records === 0 ? "No records" : `${first.toLocaleString()}–${last.toLocaleString()} of ${total_records.toLocaleString()}${total_is_exact ? "" : "+"}`}
      </p>
      <div className="flex items-center gap-2">
        <Select
          aria-label="Records per page"
          className="h-9 w-36 shrink-0 rounded-lg"
          options={PAGE_SIZES}
          value={String(per_page)}
          disabled={disabled}
          onChange={(event) => onPerPageChange(Number(event.target.value))}
        />
        <Button variant="secondary" size="sm" icon="chevronLeft" disabled={disabled || page <= 1} onClick={() => onPageChange(page - 1)} title="Previous page">
          <span className="hidden sm:inline">Previous</span>
        </Button>
        <span className="whitespace-nowrap px-1 tabular-nums">
          {page} / {Math.max(total_pages, 1)}
          {total_is_exact ? "" : "+"}
        </span>
        <Button variant="secondary" size="sm" disabled={disabled || !has_more_page || page >= maxPage} onClick={() => onPageChange(page + 1)}>
          Next
        </Button>
      </div>
    </div>
  );
}
