import { BATCH_STATUS_LABELS } from "@/modules/learning/common/labels";
import type { BatchFilters as Filters } from "@/modules/learning/batches/types";
import { Button, FilterRow, FilterSelect } from "@/shared/ui";

const STATUS_OPTIONS = Object.entries(BATCH_STATUS_LABELS).map(([value, label]) => ({ value, label }));

interface BatchFiltersProps {
  filters: Filters;
  activeCount: number;
  update(changes: Record<string, string | undefined>): void;
  reset(): void;
}

/** No free-text search: learning-service's list endpoints only filter by status. */
export function BatchFilters({ filters, activeCount, update, reset }: BatchFiltersProps) {
  return (
    <FilterRow activeCount={activeCount}>
      <FilterSelect label="Status" value={filters.status} options={STATUS_OPTIONS} onChange={(value) => update({ status: value })} />
      {activeCount > 0 && (
        <Button variant="ghost" onClick={reset}>
          Clear ({activeCount})
        </Button>
      )}
    </FilterRow>
  );
}
