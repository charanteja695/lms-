import { JOB_STATUS_LABELS, VERDICT_LABELS } from "@/modules/code-execution/common/labels";
import type { ReviewFilters as Filters } from "@/modules/code-execution/review/types";
import { Button, Checkbox, FilterRow, FilterSelect } from "@/shared/ui";

const STATUS_OPTIONS = Object.entries(JOB_STATUS_LABELS).map(([value, label]) => ({ value, label }));
const VERDICT_OPTIONS = Object.entries(VERDICT_LABELS).map(([value, label]) => ({ value, label }));

interface ReviewFiltersProps {
  filters: Filters;
  activeCount: number;
  update(changes: Record<string, string | boolean | undefined>): void;
  reset(): void;
}

/** No free-text search over student/problem: filters mirror code-execution-service's own query params. */
export function ReviewFilters({ filters, activeCount, update, reset }: ReviewFiltersProps) {
  return (
    <FilterRow activeCount={activeCount}>
      <FilterSelect label="Status" value={filters.status} options={STATUS_OPTIONS} onChange={(value) => update({ status: value })} />
      <FilterSelect label="Verdict" value={filters.verdict} options={VERDICT_OPTIONS} onChange={(value) => update({ verdict: value })} />
      <Checkbox label="Flagged only" checked={filters.flagged ?? false} onChange={(event) => update({ flagged: event.target.checked || undefined })} />
      {activeCount > 0 && (
        <Button variant="ghost" onClick={reset}>
          Clear ({activeCount})
        </Button>
      )}
    </FilterRow>
  );
}
