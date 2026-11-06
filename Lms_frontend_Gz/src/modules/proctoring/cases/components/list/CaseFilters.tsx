import { CASE_STATUS_LABELS } from "@/modules/proctoring/common/labels";
import type { CaseFilters as Filters } from "@/modules/proctoring/cases/types";
import { Button, Checkbox, FilterRow, FilterSelect } from "@/shared/ui";

const STATUS_OPTIONS = Object.entries(CASE_STATUS_LABELS).map(([value, label]) => ({ value, label }));

interface CaseFiltersProps {
  filters: Filters;
  activeCount: number;
  update(changes: Record<string, string | boolean | undefined>): void;
  reset(): void;
}

export function CaseFilters({ filters, activeCount, update, reset }: CaseFiltersProps) {
  return (
    <FilterRow activeCount={activeCount}>
      <FilterSelect label="Status" value={filters.status} options={STATUS_OPTIONS} onChange={(value) => update({ status: value })} />
      <Checkbox label="Overdue only" checked={filters.overdue ?? false} onChange={(event) => update({ overdue: event.target.checked || undefined })} />
      {activeCount > 0 && (
        <Button variant="ghost" onClick={reset}>
          Clear ({activeCount})
        </Button>
      )}
    </FilterRow>
  );
}
