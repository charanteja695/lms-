import { JOB_STATUS_LABELS, VERDICT_LABELS } from "@/modules/code-execution/common/labels";
import type { SubmissionFilters as Filters } from "@/modules/code-execution/submissions/types";
import { Button, FilterRow, FilterSelect } from "@/shared/ui";

const STATUS_OPTIONS = Object.entries(JOB_STATUS_LABELS).map(([value, label]) => ({ value, label }));
const VERDICT_OPTIONS = Object.entries(VERDICT_LABELS).map(([value, label]) => ({ value, label }));

interface SubmissionFiltersProps {
  filters: Filters;
  activeCount: number;
  update(changes: Record<string, string | undefined>): void;
  reset(): void;
}

/** No free-text search: code-execution-service's list endpoints only filter by status/verdict/problem. */
export function SubmissionFilters({ filters, activeCount, update, reset }: SubmissionFiltersProps) {
  return (
    <FilterRow activeCount={activeCount}>
      <FilterSelect label="Status" value={filters.status} options={STATUS_OPTIONS} onChange={(value) => update({ status: value })} />
      <FilterSelect label="Verdict" value={filters.verdict} options={VERDICT_OPTIONS} onChange={(value) => update({ verdict: value })} />
      {activeCount > 0 && (
        <Button variant="ghost" onClick={reset}>
          Clear ({activeCount})
        </Button>
      )}
    </FilterRow>
  );
}
