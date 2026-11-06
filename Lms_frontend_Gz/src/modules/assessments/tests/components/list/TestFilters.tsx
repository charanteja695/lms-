import { TEST_KIND_LABELS, TEST_STATUS_LABELS } from "@/modules/assessments/common/labels";
import type { TestFilters as Filters } from "@/modules/assessments/tests/types";
import { FilterBar, FilterSelect } from "@/shared/ui";

const KIND_OPTIONS = Object.entries(TEST_KIND_LABELS).map(([value, label]) => ({ value, label }));
const STATUS_OPTIONS = Object.entries(TEST_STATUS_LABELS).map(([value, label]) => ({ value, label }));

interface TestFiltersProps {
  filters: Filters;
  activeCount: number;
  update(changes: Record<string, string | undefined>): void;
  reset(): void;
}

export function TestFilters({ filters, activeCount, update, reset }: TestFiltersProps) {
  return (
    <FilterBar
      search={filters.search ?? ""}
      onSearch={(value) => update({ search: value || undefined })}
      searchPlaceholder="Search by title"
      activeCount={activeCount}
      onReset={reset}
      primary={
        <>
          <FilterSelect label="Kind" value={filters.kind} options={KIND_OPTIONS} onChange={(value) => update({ kind: value })} />
          <FilterSelect label="Status" value={filters.status} options={STATUS_OPTIONS} onChange={(value) => update({ status: value })} />
        </>
      }
    />
  );
}
